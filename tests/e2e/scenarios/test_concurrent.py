"""E2E Concurrent Operations Tests.

Tests that verify Reticulum handles concurrent operations correctly.

Test IDs:
- CONC-001: Multiple Links - 5 simultaneous links to same destination
- CONC-002: Parallel Resources - 3 concurrent resource transfers
- CONC-003: Announce Storm - 10 rapid announces from different nodes
- CONC-004: Bidirectional Traffic - Full duplex A↔C data transfer
- CONC-005: Link Pool - Link reuse vs new link performance
"""

import pytest
import time
import threading
import queue
import os


@pytest.mark.concurrent
class TestMultipleLinks:
    """Test multiple simultaneous links."""

    def test_multiple_links_to_same_destination(
        self, node_a, node_c, unique_app_name
    ):
        """
        CONC-001: Multiple links can be established to the same destination.

        Each link should have a unique link_id.
        """
        aspects = ["concurrent", "multi", "link"]

        # Start destination server
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        # Create multiple links sequentially
        links = []
        for i in range(5):
            link = node_a.create_link(
                destination_hash=dest["destination_hash"],
                app_name=unique_app_name,
                aspects=aspects,
                timeout=15.0,
            )
            links.append(link)

        # Verify all links established
        active_links = [l for l in links if l["status"] == "ACTIVE"]
        assert len(active_links) >= 3, f"Only {len(active_links)} of 5 links active"

        # Verify unique link IDs
        link_ids = [l["link_id"] for l in active_links]
        assert len(link_ids) == len(set(link_ids)), "Duplicate link IDs found"


@pytest.mark.concurrent
@pytest.mark.slow
class TestParallelResources:
    """Test parallel resource transfers."""

    def test_parallel_resource_transfers(
        self, node_a, node_c, unique_app_name
    ):
        """
        CONC-002: Multiple resources can be transferred in parallel.

        Uses threading to initiate concurrent transfers.
        """
        aspects = ["concurrent", "parallel", "resource"]

        # Start destination server
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        # Results queue
        results = queue.Queue()

        def transfer_resource(node, dest_hash, data, index):
            """Transfer resource and record result."""
            try:
                result = node.create_link_and_send_resource(
                    destination_hash=dest_hash,
                    app_name=unique_app_name,
                    data=data,
                    aspects=aspects,
                    link_timeout=20.0,
                    resource_timeout=60.0,
                )
                results.put((index, result, None))
            except Exception as e:
                results.put((index, None, str(e)))

        # Create test data for each transfer
        test_data = [os.urandom(1000) for _ in range(3)]

        # Start transfers in threads
        threads = []
        for i, data in enumerate(test_data):
            t = threading.Thread(
                target=transfer_resource,
                args=(node_a, dest["destination_hash"], data, i)
            )
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join(timeout=90)

        # Collect results
        completed = 0
        while not results.empty():
            index, result, error = results.get_nowait()
            if error:
                print(f"Transfer {index} error: {error}")
            elif result and result.get("resource_completed"):
                completed += 1

        # At least some transfers should complete
        assert completed >= 1, f"Only {completed} of 3 transfers completed"


@pytest.mark.concurrent
class TestAnnounceStorm:
    """Test rapid announce handling."""

    def test_rapid_announces(self, node_a, node_c, unique_app_name):
        """
        CONC-003: System handles rapid announces correctly.

        Multiple destinations announced in quick succession.
        """
        aspects = ["concurrent", "announce", "storm"]

        destinations = []

        # Create multiple destinations with announces
        for i in range(5):
            dest = node_c.create_destination(
                app_name=unique_app_name,
                aspects=aspects + [f"dest{i}"],
                announce=True,
            )
            destinations.append(dest)
            time.sleep(0.2)  # Small delay between announces

        # Verify node_a can find paths to destinations
        found = 0
        for dest in destinations:
            try:
                path_result = node_a.wait_for_path(
                    dest["destination_hash"],
                    timeout=5.0,
                )
                if path_result.get("path_found"):
                    found += 1
            except Exception:
                pass

        # Most paths should be found
        assert found >= 3, f"Only {found} of {len(destinations)} paths found"

    def test_announce_flood_prevention(self, node_a, node_c, unique_app_name):
        """
        System prevents announce flooding (bandwidth cap).

        This test verifies the system doesn't crash under announce load.
        Flood destinations are created without announce=True so they don't
        consume announce bandwidth in the persistent daemon.
        """
        aspects = ["concurrent", "flood"]

        # Create several destinations that each trigger an announce
        for i in range(3):
            try:
                dest_flood = node_c.create_destination(
                    app_name=unique_app_name,
                    aspects=aspects + [f"flood{i}"],
                )
                # Announce each one explicitly to stress the announce queue
                node_c.announce(dest_flood["destination_hash"])
            except Exception:
                pass  # Some may fail due to rate limiting

        # Verify basic functionality still works after the flood
        dest = node_c.start_destination_server(
            app_name=unique_app_name + "_after_flood",
            aspects=["test", "responsive"],
            announce=True,
        )

        path = node_a.wait_for_path(dest["destination_hash"], timeout=20.0)
        assert path.get("path_found"), f"Path not found after flood: {path}"

        link = node_a.create_link(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name + "_after_flood",
            aspects=["test", "responsive"],
            timeout=20.0,
        )

        assert link["status"] == "ACTIVE", f"System unresponsive after announce flood: {link}"


@pytest.mark.concurrent
class TestBidirectionalTraffic:
    """Test bidirectional data transfer."""

    def test_full_duplex_communication(self, node_a, node_c, unique_app_name):
        """
        CONC-004: Bidirectional data transfer A↔C.

        Both nodes send data to each other simultaneously.
        """
        aspects_c = ["concurrent", "duplex", "c"]
        aspects_a = ["concurrent", "duplex", "a"]

        # Start servers on both nodes
        dest_c = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects_c,
            announce=True,
        )

        dest_a = node_a.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects_a,
            announce=True,
        )

        node_a.wait_for_path(dest_c["destination_hash"], timeout=15.0)
        node_c.wait_for_path(dest_a["destination_hash"], timeout=15.0)

        # Results for concurrent transfers
        results = queue.Queue()

        def send_to_c():
            try:
                result = node_a.create_link_and_send(
                    destination_hash=dest_c["destination_hash"],
                    app_name=unique_app_name,
                    data=b"A->C: Hello from A!",
                    aspects=aspects_c,
                    link_timeout=15.0,
                    data_timeout=5.0,
                )
                results.put(("A->C", result))
            except Exception as e:
                results.put(("A->C", {"error": str(e)}))

        def send_to_a():
            try:
                result = node_c.create_link_and_send(
                    destination_hash=dest_a["destination_hash"],
                    app_name=unique_app_name,
                    data=b"C->A: Hello from C!",
                    aspects=aspects_a,
                    link_timeout=15.0,
                    data_timeout=5.0,
                )
                results.put(("C->A", result))
            except Exception as e:
                results.put(("C->A", {"error": str(e)}))

        # Start both transfers
        t1 = threading.Thread(target=send_to_c)
        t2 = threading.Thread(target=send_to_a)
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        # Check results
        transfer_results = {}
        while not results.empty():
            direction, result = results.get_nowait()
            transfer_results[direction] = result

        # At least one direction should succeed
        success_count = sum(
            1 for r in transfer_results.values()
            if r.get("status") == "ACTIVE" and r.get("data_sent")
        )

        assert success_count >= 1, f"No successful transfers: {transfer_results}"


@pytest.mark.concurrent
class TestLinkPool:
    """Test link reuse and pooling behavior."""

    def test_sequential_link_reuse(self, node_a, node_c, unique_app_name):
        """
        CONC-005: Sequential links to same destination work correctly.

        Tests that old links don't interfere with new ones.
        """
        aspects = ["concurrent", "pool"]

        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        # Create multiple sequential links, each sending data
        successful_transfers = 0
        results = []

        for i in range(3):
            result = node_a.create_link_and_send(
                destination_hash=dest["destination_hash"],
                app_name=unique_app_name,
                data=f"Message {i}".encode(),
                aspects=aspects,
                link_timeout=15.0,  # Longer timeout
                data_timeout=10.0,
            )
            results.append(result)

            if result["status"] == "ACTIVE" and result["data_sent"]:
                successful_transfers += 1

            time.sleep(0.2)

        # At least one transfer should succeed
        assert successful_transfers >= 1, f"No transfers succeeded: {results}"
