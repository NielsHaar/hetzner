import argparse
import locale
import os
import re
import sys
from HTMLParser import HTMLParser

import configparser

from hetzner.robot import RobotWebInterface

RE_CSRF_TOKEN = re.compile(
    r'<input[^>]*?name="_csrf_token"[^>]*?value="([^">]+)"'
)

RE_DNS_ENTRIES = re.compile(
    r'<textarea[^>]*name="zonefile"[^>]*>([^<]*)</textarea>',
    re.M
)

dir_path = os.path.dirname(os.path.realpath(__file__))


class SubCommand(object):
    command = None
    description = None
    long_description = None
    option_list = []

    def putline(self, line):
        data = line + u"\n"
        try:
            sys.stdout.write(data)
        except UnicodeEncodeError:
            preferred = locale.getpreferredencoding()
            sys.stdout.write(data.encode(preferred, 'replace'))

    def execute(self, parser, args):
        pass


def make_option(*args, **kwargs):
    return (args, kwargs)


class ModifyDnsFile(SubCommand):
    command = 'dns'
    description = "Get or set dns file"
    long_description = ("Get or Set dns entries for hetzner robot dns zones.")
    option_list = [
        make_option('-a', '--action', dest='action', metavar='ACTION',
                    default=False, help="The action to take. \"store\" to save to hetzner, \"load\" to load from hetzner"),
        make_option('-c', '--config-file', dest='config', metavar='CONFIG',
                    default=dir_path + "/dns.config", help="Set the config file"),
        make_option('-w', '--working-dir', dest='working_dir', metavar='WDIR',
                    default=dir_path, help="Set the working directory (files will be stored here)"),
        make_option('-z', '--zone-id', dest='zone_id', metavar='ZONE',
                    default=False, help="The dns zone id"),
    ]

    def execute(self, parser, args):
        config_file = args.config
        working_dir = args.working_dir
        zone_id = args.zone_id

        # Config File
        config = self.load_config(config_file)
        hetzner_user = self.config_hetzner_user(config)
        hetzner_pass = self.config_hetzner_pass(config)

        # File name of db file
        file_name_db = self.db_path(working_dir, zone_id)

        # Debug
        # print "user: " + hetzner_user
        # print "pass: " + hetzner_pass
        # print "file: " + file_name_db
        # print "zone: " + zone_id

        # Run actions
        action = args.action
        if "store" == action.lower():
            # print "running store"
            self.store_dns_file(hetzner_user, hetzner_pass, file_name_db, zone_id)
        elif "load" == action.lower():
            # print "running load"
            self.load_dns_file(hetzner_user, hetzner_pass, file_name_db, zone_id)
        else:
            print "unable to determine action: " + action
            exit(10)

    def load_config(self, config_file):
        config = configparser.ConfigParser()
        config.read(config_file)

        return config

    def config_hetzner_user(self, config):
        return config['hetzner']['UserName']

    def config_hetzner_pass(self, config):
        return config['hetzner']['Password']

    def db_path(self, working_dir, zone_id):
        return working_dir + "/" + zone_id + ".db"

    def store_dns_file(self, hetzner_user, hetzner_pass, file_name_db, zone_id):
        web = RobotWebInterface(user=hetzner_user, passwd=hetzner_pass)
        web.login()

        response = web.request(path="/dns/update/id/" + zone_id, method="GET")
        content = response.read()
        token = RE_CSRF_TOKEN \
            .search(str(content)) \
            .group(1)

        db_input = open(file_name_db, "r")
        dns = db_input.read()
        db_input.close()

        response = web.request(path="/dns/update", method="POST", data=[
            ("id", zone_id),
            ("zonefile", dns),
            ("_csrf_token", token),
        ])
        if response.status != 200:
            print "Error status was: " + response.status
            print "Response was: " + response.read()
            exit(11)

    def load_dns_file(self, hetzner_user, hetzner_pass, file_name_db, zone_id):
        web = RobotWebInterface(user=hetzner_user, passwd=hetzner_pass)
        web.login()

        response = web.request(path="/dns/update/id/" + zone_id, method="GET")
        content = response.read()
        dns = RE_DNS_ENTRIES \
            .search(str(content)) \
            .group(1)

        html_parser = HTMLParser()
        dns = html_parser.unescape(dns)

        db_output = open(file_name_db, "w")
        db_output.write(str(dns))
        db_output.close()

        print file_name_db


def main():
    subcommands = [
        ModifyDnsFile
    ]

    common_parser = argparse.ArgumentParser(
        description="Common options",
        add_help=False
    )

    common_parser.add_argument_group(title="global options")

    parser = argparse.ArgumentParser(
        description="Hetzner Robot commandline interface",
        prog='hetznerctl',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        parents=[common_parser]
    )

    subparsers = parser.add_subparsers(
        title="available commands",
        metavar="command",
        help="description",
    )

    for cmd in subcommands:
        subparser = subparsers.add_parser(
            cmd.command,
            help=cmd.description,
            description=cmd.long_description,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            parents=[common_parser]
        )
        for args, kwargs in cmd.option_list:
            subparser.add_argument(*args, **kwargs)
        subparser.set_defaults(cmdclass=cmd)

    args = parser.parse_args()

    if getattr(args, 'cmdclass', None) is None:
        parser.print_help()
        parser.exit(1)

    subcommand = args.cmdclass()

    subcommand.execute(parser, args)


if __name__ == '__main__':
    main()
