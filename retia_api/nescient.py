from datetime import datetime
from timeit import default_timer as timer

import numpy as np
import pandas as pd

from retia_api.databases.models import Detector
from retia_api.helpers.elasticclient import get_netflow_data_at_nearest_time
from retia_api.helpers.logging import activity_log
from retia_api.helpers.operation import (
    createAcl,
    delAcl,
    getAclDetail,
    getAclList,
    setAclDetail,
)
from retia_api.helpers.utils import getprotobynumber


def core(data_to_be_used: list, detector_instance: Detector):
    sampling_interval = detector_instance.sampling_interval
    window_size = detector_instance.window_size

    A1_all = []
    A2_all = []
    A3_all = []
    A4_all = []

    for bucket in data_to_be_used:
        A1_all.append([bucket["key"], bucket["packets"]["value"]])
        A2_all.append([bucket["key"], bucket["USIP"]["value"]])
        A3_all.append(
            [
                bucket["key"],
                (
                    0
                    if bucket["USIP"]["value"] == 0 or bucket["UDIP"]["value"] == 0
                    else bucket["USIP"]["value"] / bucket["UDIP"]["value"]
                ),
            ]
        )
        A4_all.append(
            [
                bucket["key"],
                (
                    0
                    if bucket["USIP"]["value"] == 0 or bucket["UPR"]["value"] == 0
                    else bucket["USIP"]["value"] / bucket["UPR"]["value"]
                ),
            ]
        )

    A_all = (
        pd.DataFrame(A1_all),
        pd.DataFrame(A2_all),
        pd.DataFrame(A3_all),
        pd.DataFrame(A4_all),
    )

    Threshold_all = []
    N_all = []
    beta_all = []

    j_to_end = range(len(A1_all))

    for A in A_all:
        # Init values
        K = window_size
        T = sampling_interval
        beta = 1.5
        j = 0
        current_threshold_array = list()
        current_N_array = list()
        current_beta_array = list()

        A_list = A.iloc[:, 1].to_list()
        safe_A_list = [*A_list, *([0] * K * T)]

        current_moving_A = A.iloc[j : j + K, 1].to_list()
        current_moving_mean = np.mean(current_moving_A)
        current_moving_variance = np.std(current_moving_A)
        current_threshold = (current_moving_mean + current_moving_variance) * beta

        current_threshold_array.append([j, current_threshold])
        current_beta_array.append([j, beta])

        # while j <= K*T-1 and j < len(A1_all.iloc[:, 0].to_list()):
        while j < len(A1_all):
            if j < 0 and j % K * T == 0:
                beta = 1.5
                current_moving_A = safe_A_list[j : j + K]
                current_moving_mean = np.mean(current_moving_A)
                current_moving_variance = np.std(current_moving_A)
                current_threshold = (
                    current_moving_mean + current_moving_variance
                ) * beta

                current_threshold_array.append([j, current_threshold])
                current_beta_array.append([j, beta])
                if safe_A_list[j : j + 1][0] > current_threshold:
                    current_N_array.append([j, True])
                else:
                    current_N_array.append([j, False])
            else:
                if safe_A_list[j : j + 1][0] > current_threshold:
                    current_N_array.append([j, True])
                else:
                    current_N_array.append([j, False])
                j = j + 1
                current_j = j
                previous_j = j - 1
                previous_moving_mean = np.mean(safe_A_list[previous_j : previous_j + K])
                current_moving_mean = np.mean(safe_A_list[current_j : current_j + K])
                if current_moving_mean > 2 * previous_moving_mean:
                    beta = beta + 0.5
                    current_threshold = (
                        current_moving_mean
                        + np.std(safe_A_list[current_j : current_j + K])
                    ) / beta
                else:
                    beta = beta - 0.5
                    if beta < 1.0:
                        beta = 1
                    current_threshold = (
                        current_moving_mean
                        + np.std(safe_A_list[current_j : current_j + K])
                    ) * beta
                current_threshold_array.append([current_j, current_threshold])
                current_beta_array.append([j, beta])

        Threshold_all.append(current_threshold_array)
        N_all.append(current_N_array)
        beta_all.append(current_beta_array)
    handle_result(j_to_end, N_all, data_to_be_used, detector_instance)


def handle_result(j, N, data, detector_instance: Detector):
    for idx in j:
        timestamp = int(str(data[idx]["key"])[:-3])
        if (
            N[0][idx][1] is True
            and N[1][idx][1] is True
            and N[2][idx][1] is True
            and N[3][idx][1] is True
        ):
            positive_traffic = get_netflow_data_at_nearest_time(
                timestamp,
                detector_instance.elastic_host,
                detector_instance.elastic_index,
            )

            report = "src: {}, dest: {}, dest_port: {}, L4_proto: {}".format(
                positive_traffic["source_ipv4_address"],
                positive_traffic["destination_ipv4_address"],
                positive_traffic["destination_transport_port"],
                getprotobynumber(positive_traffic["protocol_identifier"]),
            )
            detection_result = "Target: %s, message:POSITIVE %s" % (
                detector_instance.device.mgmt_ipaddr,
                report,
            )

            print(detection_result)
            activity_log(
                "warning",
                detector_instance.device.hostname,
                "detector",
                detection_result,
            )

            ## DDoS Mitigation
            acl_name = "retia_dos_mitigation"
            conn_strings = {
                "ipaddr": detector_instance.device.mgmt_ipaddr,
                "port": detector_instance.device.port,
                "credential": (
                    detector_instance.device.username,
                    detector_instance.device.secret,
                ),
            }

            ddos_mitigation_acl_res = getAclDetail(
                conn_strings=conn_strings, req_to_show={"name": acl_name}
            )
            ddos_mitigation_acl = ddos_mitigation_acl_res["body"]

            # get latest sequnce number to use
            if (
                ddos_mitigation_acl_res["code"] == 200
                or not "error" in ddos_mitigation_acl
            ):
                if ddos_mitigation_acl_res["code"] == 404:
                    createAcl(
                        conn_strings=conn_strings, req_to_create={"name": acl_name}
                    )
                    ddos_mitigation_acl["name"] = acl_name
                    ddos_mitigation_acl["rules"] = []
                    ddos_mitigation_acl["apply_to_interface"] = {
                        detector_instance.device_interface_to_server: ["out"]
                    }
                    next_sequence_numbers = 1
                else:
                    sequence_numbers = []
                    for rule in ddos_mitigation_acl["rules"]:
                        sequence_numbers.append(int(rule["sequence"]))
                    next_sequence_numbers = str(max(sequence_numbers) + 1)
                ddos_mitigation_acl["rules"].append(
                    {
                        "sequence": next_sequence_numbers,
                        "action": "deny",
                        "prefix": negative_traffic["source_ipv4_address"],
                        "wildcard": None,
                    }
                )
                setAclDetail(
                    conn_strings=conn_strings, req_to_change=ddos_mitigation_acl
                )

        else:
            negative_traffic = get_netflow_data_at_nearest_time(
                timestamp,
                detector_instance.elastic_host,
                detector_instance.elastic_index,
            )

            report = "src: {}, dest: {}, dest_port: {}, L4_proto: {}".format(
                negative_traffic["source_ipv4_address"],
                negative_traffic["destination_ipv4_address"],
                negative_traffic["destination_transport_port"],
                getprotobynumber(negative_traffic["protocol_identifier"]),
            )
            detection_result = "Target: %s, message:NEGATIVE %s" % (
                detector_instance.device.mgmt_ipaddr,
                report,
            )
            print(detection_result)
            activity_log(
                "info", detector_instance.device.hostname, "detector", detection_result
            )
