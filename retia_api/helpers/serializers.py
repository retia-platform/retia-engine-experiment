from rest_framework import serializers

from retia_api.databases.models import ActivityLog, Detector, Device


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = [
            "hostname",
            "brand",
            "device_type",
            "mgmt_ipaddr",
            "port",
            "username",
            "secret",
            "created_at",
            "modified_at",
        ]


class DetectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Detector
        fields = [
            "device",
            "device_interface_to_filebeat",
            "device_interface_to_server",
            "window_size",
            "sampling_interval",
            "elastic_host",
            "elastic_index",
            "filebeat_host",
            "filebeat_port",
            "created_at",
            "modified_at",
        ]


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = ["time", "severity", "instance", "category", "messages"]
