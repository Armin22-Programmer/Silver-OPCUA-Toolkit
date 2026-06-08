# backend/app/api/routes/tags.py

from fastapi import APIRouter, HTTPException
from asyncua import ua
from asyncua.common.node import Node
from app.opcua.manager import opcua_manager
from pydantic import BaseModel
import re

router = APIRouter(prefix="/api/v1/tags", tags=["tags"])


class NodeInfo(BaseModel):
    node_id: str
    name: str
    node_class: str
    value: str | None


def parse_node_id(client, node_id_str: str) -> Node:
    """
    Convert a node_id string to an asyncua Node object.
    Supports:
      - Standard format:  ns=2;i=1   or  ns=3;s=MyTag
      - asyncua repr:     NodeId(Identifier=1, NamespaceIndex=2, ...)
      - asyncua repr:     NodeId(Identifier='PLC', NamespaceIndex=3, ...)
    """
    if node_id_str.startswith("NodeId("):
        identifier_match = re.search(r"Identifier=(\w+|'[^']*')", node_id_str)
        namespace_match  = re.search(r"NamespaceIndex=(\d+)", node_id_str)

        if identifier_match and namespace_match:
            ns    = namespace_match.group(1)
            ident = identifier_match.group(1).strip("'")

            if ident.isdigit():
                node_id_str = f"ns={ns};i={ident}"
            else:
                node_id_str = f"ns={ns};s={ident}"

    return client.get_node(node_id_str)


@router.get("/{connection_id}/browse", response_model=list[NodeInfo])
async def browse_tags(connection_id: int, node_id: str | None = None):
    """
    Browse the OPC UA node tree for a given connection.
    If node_id is provided, browse children of that node.
    If not provided, start from the root Objects folder.
    """
    client = opcua_manager.get_client(connection_id)
    if not client:
        raise HTTPException(
            status_code=400,
            detail="Connection is not active. Please connect first."
        )

    try:
        if node_id:
            parent_node = parse_node_id(client, node_id)
        else:
            parent_node = client.get_objects_node()

        children = await parent_node.get_children()
        nodes = []

        for child in children:
            browse_name = await child.read_browse_name()
            name        = browse_name.Name

            node_class     = await child.read_node_class()
            node_class_str = "Object" if node_class == ua.NodeClass.Object else "Variable"

            value = None
            if node_class == ua.NodeClass.Variable:
                try:
                    raw_value = await child.read_value()
                    value = str(raw_value)
                except Exception:
                    value = "N/A"

            nodes.append(NodeInfo(
                node_id=str(child.nodeid),
                name=name,
                node_class=node_class_str,
                value=value,
            ))

        return nodes

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Browse failed: {str(e)}")
