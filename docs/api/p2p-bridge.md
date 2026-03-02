# P2P Bridge API

## ArgosBridge

::: src.connectivity.p2p_bridge.ArgosBridge
    options:
      show_source: false
      members:
        - start
        - register_transport
        - transport_status
        - network_status
        - network_telemetry
        - routing_tuning_report
        - set_routing_weight
        - set_failover_limit
        - route_query
        - sync_skills_from_network
        - connect_to

## NodeProfile

::: src.connectivity.p2p_bridge.NodeProfile
    options:
      show_source: false

## NodeRegistry

::: src.connectivity.p2p_bridge.NodeRegistry
    options:
      show_source: false

## TaskDistributor

::: src.connectivity.p2p_bridge.TaskDistributor
    options:
      show_source: false
      members:
        - pick_node_for
        - top_candidates
        - route_task
        - update_weight
        - tuning_report

## p2p_protocol_roadmap

::: src.connectivity.p2p_bridge.p2p_protocol_roadmap
    options:
      show_source: false
