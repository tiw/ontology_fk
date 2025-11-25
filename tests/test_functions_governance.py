from typing import Dict

import pytest

from ontology_framework.core import (
    Function,
    LinkType,
    ObjectInstance,
    ObjectSet,
    ObjectType,
    ObjectTypeSpec,
    Ontology,
    PropertyType,
)
from ontology_framework.exceptions import ValidationError
from ontology_framework.osdk import OntologySDK


def _build_order_type() -> ObjectType:
    return (
        ObjectType(api_name="order", display_name="Order", primary_key="order_id")
        .add_property("order_id", PropertyType.STRING)
        .add_property("merchant_id", PropertyType.STRING)
        .add_property("rider_id", PropertyType.STRING)
        .add_property("status", PropertyType.STRING)
    )


def _register_function(
    ontology: Ontology, api_name: str, inputs: Dict[str, ObjectTypeSpec], logic
):
    fn = Function(api_name=api_name, display_name=api_name, logic=logic)
    for arg_name, type_spec in inputs.items():
        fn.add_input(arg_name, type_spec)
    ontology.register_function(fn)


def test_link_validation_filters_objects():
    ontology = Ontology()
    device_type = (
        ObjectType(api_name="Device", display_name="Device", primary_key="device_id")
        .add_property("device_id", PropertyType.STRING)
        .add_property("name", PropertyType.STRING)
    )
    status_type = (
        ObjectType(api_name="Status", display_name="Status", primary_key="status_id")
        .add_property("status_id", PropertyType.STRING)
        .add_property("device_id", PropertyType.STRING)
    )
    ontology.register_object_type(device_type)
    ontology.register_object_type(status_type)

    link = LinkType(
        api_name="DeviceHasStatus",
        display_name="Device Status",
        source_object_type="Device",
        target_object_type="Status",
        validation_functions=["validate_device_status_link"],
    )
    ontology.register_link_type(link)

    _register_function(
        ontology,
        "validate_device_status_link",
        {"device": ObjectTypeSpec("Device"), "status": ObjectTypeSpec("Status")},
        lambda device, status: device.get("device_id") == status.get("device_id"),
    )

    device = ObjectInstance("Device", "dev-1", {"device_id": "dev-1", "name": "Pump"})
    valid_status = ObjectInstance(
        "Status", "st-1", {"status_id": "st-1", "device_id": "dev-1"}
    )
    invalid_status = ObjectInstance(
        "Status", "st-2", {"status_id": "st-2", "device_id": "other"}
    )

    ontology.add_object(device)
    ontology.add_object(valid_status)
    ontology.add_object(invalid_status)

    ontology.create_link("DeviceHasStatus", "dev-1", "st-1")
    ontology.create_link("DeviceHasStatus", "dev-1", "st-2")

    device_set = ObjectSet(device_type, [device], ontology=ontology)
    result_set = device_set.search_around("DeviceHasStatus")

    results = result_set.all()
    assert len(results) == 1
    assert results[0].primary_key_value == "st-1"


def test_link_scoring_annotations():
    ontology = Ontology()
    device_type = (
        ObjectType(api_name="Device", display_name="Device", primary_key="device_id")
        .add_property("device_id", PropertyType.STRING)
    )
    status_type = (
        ObjectType(api_name="Status", display_name="Status", primary_key="status_id")
        .add_property("status_id", PropertyType.STRING)
        .add_property("health", PropertyType.INTEGER)
    )
    ontology.register_object_type(device_type)
    ontology.register_object_type(status_type)

    link = LinkType(
        api_name="DeviceHasStatus",
        display_name="Device Status",
        source_object_type="Device",
        target_object_type="Status",
        scoring_function_api_name="score_status_health",
    )
    ontology.register_link_type(link)

    _register_function(
        ontology,
        "score_status_health",
        {"status": ObjectTypeSpec("Status")},
        lambda status: status.get("health") or 0,
    )

    device = ObjectInstance("Device", "dev-1", {"device_id": "dev-1"})
    status = ObjectInstance("Status", "st-1", {"status_id": "st-1", "health": 87})
    ontology.add_object(device)
    ontology.add_object(status)
    ontology.create_link("DeviceHasStatus", "dev-1", "st-1")

    status_set = ObjectSet(device_type, [device], ontology=ontology).search_around(
        "DeviceHasStatus"
    )
    annotated = status_set.all()[0]
    assert annotated.get_annotation("function_scores")["DeviceHasStatus"] == 87


def test_osdk_enforces_function_contracts():
    ontology = Ontology()
    order_type = _build_order_type()
    ontology.register_object_type(order_type)

    order = ObjectInstance(
        "order",
        "ord-1",
        {
            "order_id": "ord-1",
            "merchant_id": "m-1",
            "rider_id": "r-1",
            "status": "CREATED",
        },
    )
    ontology.add_object(order)

    fn = Function(
        api_name="echo_status",
        display_name="Echo Status",
        logic=lambda order: order.get("status"),
    )
    fn.add_input("order", ObjectTypeSpec("order"))
    ontology.register_function(fn)

    sdk = OntologySDK(ontology)
    result = sdk.execute_function(
        "echo_status", order={"object_type": "order", "primary_key": "ord-1"}
    )
    assert result == "CREATED"

    with pytest.raises(ValidationError):
        sdk.execute_function("echo_status")

