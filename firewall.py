#!/usr/bin/env python3
import argparse
import os
import sys
from time import sleep

import grpc

# Import P4Runtime lib from parent utils dir
# Probably there's a better way of doing this.
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '../../utils/'))
import p4runtime_lib.bmv2
import p4runtime_lib.helper
from p4runtime_lib.switch import ShutdownAllSwitchConnections



def writeIpv4_lpm(p4info_helper, ingress_sw,dst_eth_addr, dst_ip_addr,port,digits):
    table_entry = p4info_helper.buildTableEntry(#p4info_helper解析器将规则转化为P4Runtime能够识别的形式
        table_name="MyIngress.ipv4_lpm",#表名
        match_fields={#匹配域
            "hdr.ipv4.dstAddr": (dst_ip_addr, digits)#若hdr.ipv4.dstAddr与dst_ip_addr匹配则执行动作，32是掩码
        },
        action_name="MyIngress.ipv4_forward",#动作名
        action_params={#传入参数
            "dstAddr":dst_eth_addr,
            "port":port,
        })
    ingress_sw.WriteTableEntry(table_entry)#将生成的匹配动作表项加入交换机

def writeDefault(p4info_helper, ingress_sw,default):
    table_entry = p4info_helper.buildTableEntry(#p4info_helper解析器将规则转化为P4Runtime能够识别的形式
        table_name="MyIngress.ipv4_lpm",#表名
        default_action=default,
        action_name="MyIngress.drop",
        action_params= { })
    ingress_sw.WriteTableEntry(table_entry)#将生成的匹配动作表项加入交换机

def writeCheck(p4info_helper, ingress_sw,port,spec,dir):
    table_entry = p4info_helper.buildTableEntry(#p4info_helper解析器将规则转化为P4Runtime能够识别的形式
        table_name="MyIngress.check_ports",#表名
        match_fields={#匹配域
            "standard_metadata.ingress_port": port,
            "standard_metadata.egress_spec": spec
        },
        action_name="MyIngress.set_direction",#动作名
        action_params={#传入参数
            "dir": dir
        })
    ingress_sw.WriteTableEntry(table_entry)#将生成的匹配动作表项加入交换机



def printGrpcError(e):
    print("gRPC Error:", e.details(), end=' ')
    status_code = e.code()
    print("(%s)" % status_code.name, end=' ')
    traceback = sys.exc_info()[2]
    print("[%s:%d]" % (traceback.tb_frame.f_code.co_filename, traceback.tb_lineno))

def main(p4info_file_path, bmv2_file_path):
    # Instantiate a P4Runtime helper from the p4info file
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)# P4InfoHelper工具类会读取并解析p4编译器编译得到的xxx.p4.p4info.txt
# bmv2_json_file_path即p4编译器编译得到的xxx.json
# txt文件中主要记录了p4程序的一些元信息，比如id等，json文件中则记载了具体的p4程序，比如stage，操作等，用于下发给交换机
    try:
        # Create a switch connection object for s1 and s2;
        # this is backed by a P4Runtime gRPC connection.
        # Also, dump all P4Runtime messages sent to switch to given txt files.
        s1 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s1',
            address='127.0.0.1:50051',
            device_id=0,
            proto_dump_file='logs/s1-p4runtime-requests.txt')
        s2 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s2',
            address='127.0.0.1:50052',
            device_id=1,
            proto_dump_file='logs/s2-p4runtime-requests.txt')

        s3 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s3',
            address='127.0.0.1:50053',
            device_id=2,
            proto_dump_file='logs/s3-p4runtime-requests.txt')

        s4 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s4',
            address='127.0.0.1:50054',
            device_id=3,
            proto_dump_file='logs/s4-p4runtime-requests.txt')
        # Send master arbitration update message to establish this controller as
        # master (required by P4Runtime before performing any other write operation)
        s1.MasterArbitrationUpdate()
        s2.MasterArbitrationUpdate()
        s3.MasterArbitrationUpdate()
        s4.MasterArbitrationUpdate()
        # Install the P4 program on the switches
        s1.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s1")
        s2.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s2")

        s3.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s3")

        s4.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s4")

        writeCheck(p4info_helper, ingress_sw=s1,port=1,spec=3,dir=0)
        writeCheck(p4info_helper, ingress_sw=s1,port=1,spec=4,dir=0)
        writeCheck(p4info_helper, ingress_sw=s1,port=2,spec=3,dir=0)
        writeCheck(p4info_helper, ingress_sw=s1,port=2,spec=4,dir=0)
        writeCheck(p4info_helper, ingress_sw=s1,port=3,spec=1,dir=1)
        writeCheck(p4info_helper, ingress_sw=s1,port=3,spec=2,dir=1)
        writeCheck(p4info_helper, ingress_sw=s1,port=4,spec=1,dir=1)
        writeCheck(p4info_helper, ingress_sw=s1,port=4,spec=2,dir=1)
        writeDefault(p4info_helper, ingress_sw=s1,default="true")
        writeIpv4_lpm(p4info_helper, ingress_sw=s1,
                  dst_eth_addr="08:00:00:00:01:11", dst_ip_addr="10.0.1.1",port=1,digits=32)
        writeIpv4_lpm(p4info_helper, ingress_sw=s1,
                  dst_eth_addr="08:00:00:00:02:22", dst_ip_addr="10.0.2.2",port=2,digits=32)
        writeIpv4_lpm(p4info_helper, ingress_sw=s1,
                  dst_eth_addr="08:00:00:00:03:00", dst_ip_addr="10.0.3.3",port=3,digits=32)
        writeIpv4_lpm(p4info_helper, ingress_sw=s1,
                  dst_eth_addr="08:00:00:00:04:00", dst_ip_addr="10.0.4.4",port=4,digits=32)


        writeDefault(p4info_helper, ingress_sw=s2,default="true")
        writeIpv4_lpm(p4info_helper, ingress_sw=s2,
                  dst_eth_addr="08:00:00:00:03:00", dst_ip_addr="10.0.1.1",port=4,digits=32)
        writeIpv4_lpm(p4info_helper, ingress_sw=s2,
                  dst_eth_addr="08:00:00:00:04:00", dst_ip_addr="10.0.2.2",port=3,digits=32)
        writeIpv4_lpm(p4info_helper, ingress_sw=s2,
                  dst_eth_addr="08:00:00:00:03:33", dst_ip_addr="10.0.3.3",port=1,digits=32)
        writeIpv4_lpm(p4info_helper, ingress_sw=s2,
                  dst_eth_addr="08:00:00:00:04:44", dst_ip_addr="10.0.4.4",port=2,digits=32)

        writeDefault(p4info_helper, ingress_sw=s3,default="true")
        writeIpv4_lpm(p4info_helper, ingress_sw=s3,
                  dst_eth_addr="08:00:00:00:01:00", dst_ip_addr="10.0.1.1",port=1,digits=32)
        writeIpv4_lpm(p4info_helper, ingress_sw=s3,
                  dst_eth_addr="08:00:00:00:01:00", dst_ip_addr="10.0.2.2",port=1,digits=32)
        writeIpv4_lpm(p4info_helper, ingress_sw=s3,
                  dst_eth_addr="08:00:00:00:02:00", dst_ip_addr="10.0.3.3",port=2,digits=32)
        writeIpv4_lpm(p4info_helper, ingress_sw=s3,
                  dst_eth_addr="08:00:00:00:02:00", dst_ip_addr="10.0.4.4",port=2,digits=32)

        writeDefault(p4info_helper, ingress_sw=s4,default="true")
        writeIpv4_lpm(p4info_helper, ingress_sw=s4,
                  dst_eth_addr="08:00:00:00:01:00", dst_ip_addr="10.0.1.1",port=2,digits=32)
        writeIpv4_lpm(p4info_helper, ingress_sw=s4,
                  dst_eth_addr="08:00:00:00:01:00", dst_ip_addr="10.0.2.2",port=2,digits=32)
        writeIpv4_lpm(p4info_helper, ingress_sw=s4,
                  dst_eth_addr="08:00:00:00:02:00", dst_ip_addr="10.0.3.3",port=1,digits=32)
        writeIpv4_lpm(p4info_helper, ingress_sw=s4,
                  dst_eth_addr="08:00:00:00:02:00", dst_ip_addr="10.0.4.4",port=1,digits=32)



    except KeyboardInterrupt:
        print(" Shutting down.")
    except grpc.RpcError as e:
        printGrpcError(e)

    ShutdownAllSwitchConnections()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='P4Runtime Controller')
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
                        type=str, action="store", required=False,
                        default='./build/firewall.p4.p4info.txt')
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
                        type=str, action="store", required=False,
                        default='./build/firewall.json')
    args = parser.parse_args()

    if not os.path.exists(args.p4info):
        parser.print_help()
        print("\np4info file not found: %s\nHave you run 'make'?" % args.p4info)
        parser.exit(1)
    if not os.path.exists(args.bmv2_json):
        parser.print_help()
        print("\nBMv2 JSON file not found: %s\nHave you run 'make'?" % args.bmv2_json)
        parser.exit(1)
    main(args.p4info, args.bmv2_json)