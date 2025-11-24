import pytest

from ontology_framework import ActionType, LinkType, ObjectType, Ontology, PropertyType


def test_object_type_registration():
    ontology = Ontology()
    obj = ObjectType(api_name="TestObj", display_name="Test Object", primary_key="id")
    obj.add_property("id", PropertyType.STRING)

    ontology.register_object_type(obj)

    retrieved = ontology.get_object_type("TestObj")
    assert retrieved is not None
    assert retrieved.api_name == "TestObj"
    assert "id" in retrieved.properties


def test_link_type_registration():
    ontology = Ontology()
    source = ObjectType(api_name="Source", display_name="Source", primary_key="id")
    target = ObjectType(api_name="Target", display_name="Target", primary_key="id")

    ontology.register_object_type(source)
    ontology.register_object_type(target)

    link = LinkType(
        api_name="SourceToTarget",
        display_name="Source To Target",
        source_object_type="Source",
        target_object_type="Target",
    )

    ontology.register_link_type(link)
    assert ontology.get_link_type("SourceToTarget") is not None


def test_link_type_validation_error():
    ontology = Ontology()
    link = LinkType(
        api_name="InvalidLink",
        display_name="Invalid Link",
        source_object_type="NonExistent",
        target_object_type="NonExistent",
    )

    with pytest.raises(ValueError):
        ontology.register_link_type(link)


def test_action_type_registration():
    ontology = Ontology()
    obj = ObjectType(api_name="TestObj", display_name="Test Object", primary_key="id")
    ontology.register_object_type(obj)

    action = ActionType(
        api_name="TestAction",
        display_name="Test Action",
        target_object_types=["TestObj"],
    )

    ontology.register_action_type(action)
    assert ontology.get_action_type("TestAction") is not None
