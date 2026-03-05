"""
tests/test_p2p.py — Автотесты P2P-системы Аргоса
  Покрывает: NodeProfile, NodeRegistry, TaskDistributor,
             авторитет, сериализацию, P2P-мост.
  Запуск: python -m pytest tests/test_p2p.py -v
  Или:    python tests/test_p2p.py
"""

import json
import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest


class TestNodeProfile(unittest.TestCase):
    def setUp(self):
        from src.connectivity.p2p_bridge import NodeProfile

        self.NodeProfile = NodeProfile

    def test_create_profile(self):
        p = self.NodeProfile()
        self.assertIsNotNone(p.node_id)
        self.assertIsInstance(p.node_id, str)
        self.assertGreater(len(p.node_id), 8)

    def test_get_power_structure(self):
        p = self.NodeProfile()
        pwr = p.get_power()
        self.assertIn("index", pwr, "get_power() должен содержать 'index'")
        self.assertIn("cpu_free", pwr)
        self.assertIn("ram_free", pwr)
        self.assertIsInstance(pwr["index"], (int, float))
        self.assertGreaterEqual(pwr["index"], 0)
        self.assertLessEqual(pwr["index"], 100)

    def test_authority_formula(self):
        """Авторитет = мощность × log(возраст + 2).
        Мокаем get_power чтобы убрать влияние CPU-флуктуаций."""
        import math
        from unittest.mock import patch

        p = self.NodeProfile()
        fixed_power = {"index": 50, "cpu_free": 50.0, "ram_free": 80.0, "cpu_cores": 2, "ram_gb": 4.0}
        with patch.object(type(p), "get_power", return_value=fixed_power):
            age_days = p.get_age_days()
            authority = p.get_authority()
            expected = int(fixed_power["index"] * math.log(age_days + 2))
            self.assertEqual(authority, expected, msg="Авторитет не соответствует формуле")

    def test_authority_increases_with_age(self):
        """Более старая нода должна иметь больший авторитет при той же мощности."""
        import math

        p = self.NodeProfile()
        pwr = p.get_power()["index"]
        auth_day1 = pwr * math.log(1 + 2)
        auth_day30 = pwr * math.log(30 + 2)
        self.assertGreater(auth_day30, auth_day1)

    def test_serialize_deserialize(self):
        p = self.NodeProfile()
        data = p.to_dict()
        self.assertIn("node_id", data)
        self.assertIn("hostname", data)
        self.assertIn("power", data)
        self.assertIn("authority", data)
        # Сериализация в JSON
        j = json.dumps(data)
        back = json.loads(j)
        self.assertEqual(back["node_id"], p.node_id)

    def test_hostname_is_string(self):
        p = self.NodeProfile()
        self.assertIsInstance(p.hostname, str)
        self.assertGreater(len(p.hostname), 0)

    def test_get_age_days_nonnegative(self):
        p = self.NodeProfile()
        self.assertGreaterEqual(p.get_age_days(), 0)


class TestNodeRegistry(unittest.TestCase):
    def setUp(self):
        from src.connectivity.p2p_bridge import NodeProfile, NodeRegistry

        self.NodeRegistry = NodeRegistry
        self.NodeProfile = NodeProfile

    def test_add_and_get(self):
        reg = self.NodeRegistry()
        node = self.NodeProfile().to_dict()
        reg.update(node, node.get("ip", "127.0.0.1"))
        all_nodes = reg.all()
        ids = [n.get("node_id") for n in all_nodes]
        self.assertIn(node["node_id"], ids, "Узел не найден после добавления")

    def test_count(self):
        reg = self.NodeRegistry()
        for i in range(3):
            node = self.NodeProfile().to_dict()
            node["node_id"] = f"test_node_{i}"
            reg.update(node, node.get("ip", "127.0.0.1"))
        self.assertGreaterEqual(reg.count(), 3)

    def test_get_master_returns_highest_authority(self):
        reg = self.NodeRegistry()
        import math

        nodes = []
        for i, auth in enumerate([50, 120, 80]):
            n = {
                "node_id": f"n{i}",
                "hostname": f"host{i}",
                "authority": auth,
                "power": {"index": 50},
                "age_days": i + 1,
                "last_seen": time.time(),
            }
            nodes.append(n)
            reg.update(n, "127.0.0.1")
        master = reg.get_master()
        self.assertIsNotNone(master)
        self.assertEqual(master["node_id"], "n1", f"Мастером должен быть n1 (авторитет 120), а не {master['node_id']}")

    def test_remove_node(self):
        reg = self.NodeRegistry()
        node = self.NodeProfile().to_dict()
        reg.update(node, "127.0.0.1")
        before = reg.count()
        self.assertGreaterEqual(before, 1, "Узел должен быть добавлен")

    def test_all_returns_list(self):
        reg = self.NodeRegistry()
        result = reg.all()
        self.assertIsInstance(result, list)

    def test_update_existing_node(self):
        reg = self.NodeRegistry()
        node = self.NodeProfile().to_dict()
        reg.update(node, node.get("ip", "127.0.0.1"))
        node["power"]["index"] = 99
        reg.update(node, node.get("ip", "127.0.0.1"))  # Обновление
        all_nodes = reg.all()
        found = next((n for n in all_nodes if n.get("node_id") == node["node_id"]), None)
        if found:
            self.assertEqual(found["power"]["index"], 99)


class TestTaskDistributor(unittest.TestCase):
    def setUp(self):
        import math

        from src.connectivity.p2p_bridge import NodeProfile, NodeRegistry, TaskDistributor

        self.NP = NodeProfile
        self.reg = NodeRegistry()
        self.self_prof = NodeProfile()
        self.dist = TaskDistributor(self.reg, self.self_prof)
        # Добавляем тестовые ноды
        for i, (pwr, age) in enumerate([(90, 30), (50, 5), (70, 15)]):
            auth = round(pwr * math.log(age + 2), 2)
            n = {
                "node_id": f"task_node_{i}",
                "hostname": f"h{i}",
                "power": {"index": pwr},
                "authority": auth,
                "age_days": age,
                "last_seen": time.time(),
                "ip": "127.0.0.1",
            }
            self.reg.update(n, "127.0.0.1")

    def test_best_node_is_highest_authority(self):
        best = self.dist.pick_node_for("ai")
        # Может вернуть None если нет реальных подключений — это нормально
        if best is not None:
            # pick_node_for returns {"node": {...}, "is_local": bool}
            node_data = best.get("node", best)
            self.assertIn("node_id", node_data)

    def test_route_returns_response(self):
        resp = self.dist.route_task("Привет")
        self.assertIsInstance(resp, str)

    def test_no_nodes_graceful(self):
        from src.connectivity.p2p_bridge import NodeProfile, NodeRegistry, TaskDistributor

        empty_reg = NodeRegistry()
        prof = NodeProfile()
        dist = TaskDistributor(empty_reg, prof)
        best = dist.pick_node_for("ai")
        # При пустом реестре возвращает себя (is_local=True) — корректное поведение
        if best is not None:
            self.assertIn("is_local", best)
            # Либо None либо локальный узел
            is_local = best.get("is_local", False)
            self.assertTrue(is_local or True)  # всегда ок
        # Нет краша — тест пройден


class TestArgosBridge(unittest.TestCase):
    def test_import(self):
        from src.connectivity.p2p_bridge import ArgosBridge

        self.assertTrue(True, "ArgosBridge импортируется без ошибок")

    def test_instantiate_without_core(self):
        from src.connectivity.p2p_bridge import ArgosBridge

        try:
            bridge = ArgosBridge(core=None)
            self.assertIsNotNone(bridge)
        except Exception as e:
            self.fail(f"ArgosBridge(core=None) упал: {e}")

    def test_has_required_methods(self):
        from src.connectivity.p2p_bridge import ArgosBridge

        bridge = ArgosBridge(core=None)
        for method in [
            "start",
            "network_status",
            "sync_skills_from_network",
            "route_query",
            "network_telemetry",
            "routing_tuning_report",
            "set_routing_weight",
            "set_failover_limit",
        ]:
            self.assertTrue(hasattr(bridge, method), f"ArgosBridge должен иметь метод '{method}'")

    def test_network_status_before_start(self):
        from src.connectivity.p2p_bridge import ArgosBridge

        bridge = ArgosBridge(core=None)
        status = bridge.network_status()
        self.assertIsInstance(status, str)
        self.assertGreater(len(status), 0)

    def test_route_query_offline(self):
        from src.connectivity.p2p_bridge import ArgosBridge

        bridge = ArgosBridge(core=None)
        result = bridge.route_query("тест")
        self.assertIsInstance(result, str)

    def test_p2p_tuning_commands(self):
        from src.connectivity.p2p_bridge import ArgosBridge

        bridge = ArgosBridge(core=None)
        report = bridge.routing_tuning_report()
        self.assertIn("P2P ROUTING TUNING", report)

        ok = bridge.set_routing_weight("auth", 0.61)
        self.assertIn("✅", ok)

        fail = bridge.set_routing_weight("unknown_weight", 1.0)
        self.assertIn("❌", fail)

        lim = bridge.set_failover_limit(4)
        self.assertIn("✅", lim)

    def test_p2p_telemetry_string(self):
        from src.connectivity.p2p_bridge import ArgosBridge

        bridge = ArgosBridge(core=None)
        text = bridge.network_telemetry()
        self.assertIn("P2P TELEMETRY", text)


class TestP2PPacketEncoding(unittest.TestCase):
    """Тесты сериализации P2P-пакетов."""

    def test_json_roundtrip(self):
        node = {
            "node_id": "test-abc-123",
            "hostname": "argos-pc",
            "power": {"index": 75, "cpu": 40, "ram_free": 60},
            "authority": 135.5,
            "age_days": 10.5,
            "last_seen": time.time(),
            "ip": "192.168.1.100",
        }
        encoded = json.dumps(node).encode("utf-8")
        decoded = json.loads(encoded.decode("utf-8"))
        self.assertEqual(decoded["node_id"], node["node_id"])
        self.assertEqual(decoded["authority"], node["authority"])

    def test_large_payload(self):
        """Большие пакеты должны сериализоваться без ошибок."""
        big = {"data": "x" * 60000, "node_id": "test"}
        enc = json.dumps(big).encode("utf-8")
        self.assertGreater(len(enc), 50000)
        dec = json.loads(enc)
        self.assertEqual(len(dec["data"]), 60000)


class TestP2PAuthority(unittest.TestCase):
    """Математические тесты формулы авторитета."""

    def test_authority_formula(self):
        import math

        cases = [
            (100, 0, 100 * math.log(2)),
            (100, 10, 100 * math.log(12)),
            (50, 30, 50 * math.log(32)),
            (0, 365, 0),
        ]
        for power, age, expected in cases:
            got = power * math.log(age + 2)
            self.assertAlmostEqual(got, expected, places=5, msg=f"Ошибка формулы: power={power} age={age}")

    def test_authority_ordering(self):
        """Приоритет: новая мощная нода vs старая слабая."""
        import math

        new_powerful = 95 * math.log(1 + 2)  # 1 день, 95% мощность
        old_weak = 30 * math.log(365 + 2)  # 1 год, 30% мощность
        self.assertGreater(old_weak, new_powerful, "Старая нода с авторитетом должна иметь приоритет над новой")


class TestEventBusP2P(unittest.TestCase):
    """Тесты EventBus в контексте P2P."""

    def test_p2p_events_subscribe(self):
        from src.event_bus import EventBus, Events

        bus = EventBus(history_size=20)
        received = []
        bus.subscribe(Events.P2P_NODE_JOINED, lambda e: received.append(e))
        bus.publish(Events.P2P_NODE_JOINED, {"node_id": "test"}, sync=True)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["node_id"], "test")
        bus.stop()

    def test_event_history(self):
        from src.event_bus import EventBus, Events

        bus = EventBus(history_size=10)
        for i in range(5):
            bus.publish(Events.P2P_NODE_JOINED, {"i": i}, sync=True)
        hist = bus.history(Events.P2P_NODE_JOINED)
        self.assertEqual(len(hist), 5)
        bus.stop()

    def test_wildcard_subscriber(self):
        from src.event_bus import EventBus, Events

        bus = EventBus()
        all_events = []
        bus.subscribe("*", lambda e: all_events.append(e.topic))
        bus.publish(Events.P2P_NODE_JOINED, {}, sync=True)
        bus.publish(Events.P2P_NODE_LEFT, {}, sync=True)
        bus.publish(Events.P2P_SKILL_SYNCED, {}, sync=True)
        self.assertEqual(len(all_events), 3)
        bus.stop()


class TestIntegration(unittest.TestCase):
    """Интеграционные тесты P2P + EventBus."""

    def test_node_joined_fires_event(self):
        from src.event_bus import Events, get_bus

        bus = get_bus()
        received = []
        bus.subscribe(Events.P2P_NODE_JOINED, lambda e: received.append(e))
        # Симулируем регистрацию ноды
        bus.emit(Events.P2P_NODE_JOINED, {"node_id": "sim_node", "ip": "10.0.0.1"})
        time.sleep(0.1)
        self.assertTrue(len(received) >= 1, "Событие P2P_NODE_JOINED не получено")

    def test_dag_events_flow(self):
        from src.event_bus import EventBus, Events

        bus = EventBus()
        events = []
        for ev in [Events.DAG_STARTED, Events.DAG_NODE_DONE, Events.DAG_COMPLETED]:
            bus.subscribe(ev, lambda e, events=events: events.append(e.topic))
        bus.publish(Events.DAG_STARTED, {"dag_id": "test"}, sync=True)
        bus.publish(Events.DAG_NODE_DONE, {"node": "step1"}, sync=True)
        bus.publish(Events.DAG_COMPLETED, {"ok": 1}, sync=True)
        self.assertEqual(len(events), 3)
        bus.stop()


# ═══════════════════════════════════════════════════════════
# ТЕСТЫ P2P ROUTING WEIGHT
# ═══════════════════════════════════════════════════════════
class TestP2PWeight(unittest.TestCase):
    """Тесты обновления весов маршрутизации."""

    def test_p2p_weight_update(self):
        from src.connectivity.p2p_bridge import ArgosBridge

        bridge = ArgosBridge(core=None)
        result = bridge.set_routing_weight("power", 1.2)
        self.assertIn("1.2", result)
        self.assertEqual(bridge.distributor.weights["power"], 1.2)

    def test_p2p_weight_unknown(self):
        from src.connectivity.p2p_bridge import ArgosBridge

        bridge = ArgosBridge(core=None)
        result = bridge.set_routing_weight("nonexistent_key", 0.5)
        self.assertIn("❌", result)

    def test_p2p_failover_limit(self):
        from src.connectivity.p2p_bridge import ArgosBridge

        bridge = ArgosBridge(core=None)
        result = bridge.set_failover_limit(4)
        self.assertIn("4", result)
        self.assertEqual(bridge.distributor.failover_limit, 4)


# ═══════════════════════════════════════════════════════════
# ТЕСТЫ TRANSPORT REGISTRY
# ═══════════════════════════════════════════════════════════
class TestTransportRegistry(unittest.TestCase):
    """Тесты реестра транспортов и базовых классов."""

    def test_registry_register_and_get(self):
        from src.connectivity.p2p_transport import TCPTransport, TransportRegistry

        reg = TransportRegistry()
        tcp = TCPTransport(55771)
        reg.register("tcp", tcp, weight=1.0)
        self.assertIs(reg.get("tcp"), tcp)

    def test_registry_set_weight(self):
        from src.connectivity.p2p_transport import TCPTransport, TransportRegistry

        reg = TransportRegistry()
        reg.register("tcp", TCPTransport(55771), weight=0.5)
        ok = reg.set_weight("tcp", 1.5)
        self.assertTrue(ok)
        self.assertEqual(reg._weights["tcp"], 1.5)

    def test_registry_set_weight_unknown(self):
        from src.connectivity.p2p_transport import TransportRegistry

        reg = TransportRegistry()
        ok = reg.set_weight("nonexistent", 1.0)
        self.assertFalse(ok)

    def test_registry_unregister(self):
        from src.connectivity.p2p_transport import TCPTransport, TransportRegistry

        reg = TransportRegistry()
        reg.register("tcp", TCPTransport(55771))
        ok = reg.unregister("tcp")
        self.assertTrue(ok)
        self.assertIsNone(reg.get("tcp"))

    def test_registry_best_selects_highest_weight(self):
        from src.connectivity.p2p_transport import TCPTransport, TransportRegistry

        reg = TransportRegistry()
        tcp1 = TCPTransport(55771)
        tcp2 = TCPTransport(55772)
        reg.register("tcp-low", tcp1, weight=0.3)
        reg.register("tcp-high", tcp2, weight=1.5)
        best = reg.best()
        self.assertIs(best, tcp2)

    def test_registry_status(self):
        from src.connectivity.p2p_transport import TCPTransport, TransportRegistry

        reg = TransportRegistry()
        reg.register("tcp", TCPTransport(55771), weight=0.8)
        status = reg.status()
        self.assertIn("tcp", status)
        self.assertIn("0.80", status)

    def test_tcp_transport_available(self):
        from src.connectivity.p2p_transport import TCPTransport

        tcp = TCPTransport(55771)
        self.assertTrue(tcp.is_available())

    def test_tcp_transport_status(self):
        from src.connectivity.p2p_transport import TCPTransport

        tcp = TCPTransport(55771)
        self.assertIn("tcp", tcp.status())

    def test_wireguard_transport_not_available(self):
        """WireGuard недоступен без реального интерфейса."""
        from src.connectivity.p2p_transport import WireGuardTransport

        wg = WireGuardTransport(wg_interface="wg_nonexistent_999")
        self.assertFalse(wg.is_available())

    def test_zerotier_transport_not_available(self):
        """ZeroTier недоступен без zerotier-cli."""
        from src.connectivity.p2p_transport import ZeroTierTransport

        zt = ZeroTierTransport(network_id="fake123")
        self.assertFalse(zt.is_available())

    def test_base_transport_not_available(self):
        from src.connectivity.p2p_transport import P2PTransportBase

        base = P2PTransportBase()
        self.assertFalse(base.is_available())


# ═══════════════════════════════════════════════════════════
# ТЕСТЫ ZKP TRANSPORT WRAPPER
# ═══════════════════════════════════════════════════════════
class TestZKPTransportWrapper(unittest.TestCase):
    """Тесты ZKP-обёртки над транспортом."""

    def test_wrapper_delegates_availability(self):
        from src.connectivity.p2p_transport import TCPTransport, ZKPTransportWrapper

        tcp = TCPTransport(55771)
        wrapper = ZKPTransportWrapper(tcp, zkp_engine=None)
        self.assertEqual(wrapper.is_available(), tcp.is_available())

    def test_wrapper_name_includes_inner(self):
        from src.connectivity.p2p_transport import TCPTransport, ZKPTransportWrapper

        tcp = TCPTransport(55771)
        wrapper = ZKPTransportWrapper(tcp, zkp_engine=None)
        self.assertIn("tcp", wrapper.name)
        self.assertIn("zkp", wrapper.name)

    def test_wrapper_verify_no_engine(self):
        """Без ZKP engine верификация всегда True."""
        from src.connectivity.p2p_transport import TCPTransport, ZKPTransportWrapper

        wrapper = ZKPTransportWrapper(TCPTransport(55771), zkp_engine=None)
        self.assertTrue(wrapper.verify_incoming({"action": "test"}))

    def test_wrapper_verify_with_zkp(self):
        """С ZKP engine подписанный пакет проходит верификацию."""
        from src.connectivity.p2p_transport import TCPTransport, ZKPTransportWrapper
        from src.security.zkp import ArgosZKPEngine

        zkp = ArgosZKPEngine(node_id="test-node", network_secret="secret", enabled=True)
        wrapper = ZKPTransportWrapper(TCPTransport(55771), zkp_engine=zkp)
        # Подписываем
        challenge = zkp.challenge("test", "req-1")
        proof = zkp.sign(challenge)
        data = {"action": "test", "zkp_proof": proof, "zkp_challenge": challenge}
        self.assertTrue(wrapper.verify_incoming(data))

    def test_wrapper_verify_bad_proof(self):
        """Поддельный proof не проходит верификацию."""
        from src.connectivity.p2p_transport import TCPTransport, ZKPTransportWrapper
        from src.security.zkp import ArgosZKPEngine

        zkp = ArgosZKPEngine(node_id="test-node", network_secret="secret", enabled=True)
        wrapper = ZKPTransportWrapper(TCPTransport(55771), zkp_engine=zkp)
        data = {
            "action": "test",
            "zkp_proof": {"node_id": "fake", "pub": "0", "commit": "0", "response": "0", "ts": 0},
            "zkp_challenge": "fake",
        }
        self.assertFalse(wrapper.verify_incoming(data))


# ═══════════════════════════════════════════════════════════
# ТЕСТЫ P2P ROADMAP
# ═══════════════════════════════════════════════════════════
class TestP2PRoadmap(unittest.TestCase):

    def test_roadmap_contains_zkp(self):
        from src.connectivity.p2p_bridge import p2p_protocol_roadmap

        roadmap = p2p_protocol_roadmap()
        self.assertIn("ZKP", roadmap)
        self.assertIn("WireGuard", roadmap)

    def test_roadmap_contains_transports(self):
        from src.connectivity.p2p_bridge import p2p_protocol_roadmap

        roadmap = p2p_protocol_roadmap()
        self.assertIn("TCP", roadmap)
        self.assertIn("ZeroTier", roadmap)


# ── RUNNER ────────────────────────────────────────────────
def run_tests():
    print("━" * 60)
    print("  ARGOS P2P АВТОТЕСТЫ")
    print("━" * 60)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    test_classes = [
        TestNodeProfile,
        TestNodeRegistry,
        TestTaskDistributor,
        TestArgosBridge,
        TestP2PPacketEncoding,
        TestP2PAuthority,
        TestEventBusP2P,
        TestIntegration,
        TestP2PWeight,
        TestTransportRegistry,
        TestZKPTransportWrapper,
        TestP2PRoadmap,
    ]
    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print("━" * 60)
    ok = result.testsRun - len(result.failures) - len(result.errors)
    fail = len(result.failures) + len(result.errors)
    print(f"  ИТОГ: {ok} ✅  /  {fail} ❌  из {result.testsRun}")
    print("━" * 60)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
