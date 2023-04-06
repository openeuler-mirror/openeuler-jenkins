import argparse
import json
import os
import sys
from src.proxy.kafka_proxy import KafkaProducerProxy


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--pkg_name', help='package name', required=True)
    parser.add_argument('-sp', '--spec_url', help='spec url', required=True)
    parser.add_argument('-b', '--build_url', help='build url', required=True)
    parser.add_argument('-i', '--pkg_id', help='package id', required=True)
    parser.add_argument('-sv', '--service', help='service info', required=True)
    parser.add_argument('-bn', '--build_number', help='build number', required=True)
    res = parser.parse_args()
    return res


if __name__ == '__main__':
    args = parse_args()
    spec_name = args.spec_url.split('/')[-1].split('.spec')[0]
    if args.pkg_name != spec_name:
        comment = """
    <table><tr><th>Check Name</th> <th>Build Result</th> <th>Build Details</th></tr><tr><td>check_consistency</td> <td>:x:<strong>FAILED</strong></td> <td rowspan=1><a href={}/console>#{}</a></td></tr></table>""".format(
            args.build_url, args.build_number)
        msg = json.dumps({
            "pkg_id": args.pkg_id,
            "success": False,
            "detail": comment
        })
        if 'test' in args.service:
            topic = 'software_pkg_ci_checked_test'
        else:
            topic = 'software_pkg_ci_checked'
        kp = KafkaProducerProxy(brokers=os.getenv('KAFKAURL'))
        kp.send(topic, 'body', json.dumps(msg).encode('utf-8'))
        print('Fail to check consistency of package name. Exit...')
        sys.exit(1)

