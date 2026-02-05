#!/usr/bin/env python3
"""
E2E Test Runner for Reticulum Protocol Conformance Tests.

Usage:
    # Run all E2E tests
    python -m tests.e2e.runner

    # Run only vector tests (no network, fastest)
    python -m tests.e2e.runner --vectors-only

    # Run interop tests with external implementation
    python -m tests.e2e.runner --interop --other-impl=/path/to/binary

    # Run specific test categories
    python -m tests.e2e.runner --category crypto
    python -m tests.e2e.runner --category packet
    python -m tests.e2e.runner --category link

    # Verbose output
    python -m tests.e2e.runner -v
    python -m tests.e2e.runner -vv
"""

import sys
import os
import argparse
import unittest
import time

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# Test module mapping
TEST_MODULES = {
    "crypto": "tests.e2e.test_crypto_vectors",
    "packet": "tests.e2e.test_packet_vectors",
    "announce": "tests.e2e.test_announce_vectors",
    "link": "tests.e2e.test_link_vectors",
    "resource": "tests.e2e.test_resource_vectors",
    "channel": "tests.e2e.test_channel_vectors",
    "interop": "tests.e2e.test_interop",
}

# Vector-only tests (no network required)
VECTOR_TESTS = ["crypto", "packet", "announce", "link", "resource", "channel"]


def discover_tests(categories=None, vectors_only=False):
    """Discover test modules to run."""
    if categories:
        modules = [TEST_MODULES[cat] for cat in categories if cat in TEST_MODULES]
    elif vectors_only:
        modules = [TEST_MODULES[cat] for cat in VECTOR_TESTS]
    else:
        modules = list(TEST_MODULES.values())

    return modules


def load_tests(modules):
    """Load test cases from modules."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for module_name in modules:
        try:
            module = __import__(module_name, fromlist=[''])
            suite.addTests(loader.loadTestsFromModule(module))
        except ImportError as e:
            print(f"Warning: Could not load {module_name}: {e}")

    return suite


def run_tests(suite, verbosity=2):
    """Run the test suite and return results."""
    runner = unittest.TextTestRunner(verbosity=verbosity)
    return runner.run(suite)


def print_summary(result, elapsed_time):
    """Print test summary."""
    print("\n" + "=" * 70)
    print("E2E TEST SUMMARY")
    print("=" * 70)

    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    passed = total - failures - errors - skipped

    print(f"Total:   {total}")
    print(f"Passed:  {passed}")
    print(f"Failed:  {failures}")
    print(f"Errors:  {errors}")
    print(f"Skipped: {skipped}")
    print(f"Time:    {elapsed_time:.2f}s")

    if result.wasSuccessful():
        print("\nRESULT: PASS")
        return 0
    else:
        print("\nRESULT: FAIL")

        if result.failures:
            print("\nFailed tests:")
            for test, _ in result.failures:
                print(f"  - {test}")

        if result.errors:
            print("\nError tests:")
            for test, _ in result.errors:
                print(f"  - {test}")

        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Reticulum E2E Protocol Conformance Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tests.e2e.runner              # Run all tests
  python -m tests.e2e.runner --vectors-only  # Run only vector tests
  python -m tests.e2e.runner --category crypto  # Run crypto tests
  python -m tests.e2e.runner --interop --other-impl=/path/to/bin
"""
    )

    parser.add_argument("-v", "--verbose", action="count", default=0,
        help="Increase verbosity (use -vv for more)")
    parser.add_argument("--vectors-only", action="store_true",
        help="Run only vector tests (no network)")
    parser.add_argument("--interop", action="store_true",
        help="Run interoperability tests")
    parser.add_argument("--other-impl", type=str,
        help="Path to external implementation binary")
    parser.add_argument("--category", type=str, action="append",
        choices=list(TEST_MODULES.keys()),
        help="Run specific test category (can be repeated)")
    parser.add_argument("--list", action="store_true",
        help="List available test categories")

    args = parser.parse_args()

    # Handle --list
    if args.list:
        print("Available test categories:")
        for name, module in TEST_MODULES.items():
            print(f"  {name}: {module}")
        return 0

    # Determine verbosity
    verbosity = 1 + args.verbose
    if verbosity > 3:
        verbosity = 3

    # Configure interop if specified
    if args.interop or args.other_impl:
        # Set global for interop module
        import tests.e2e.test_interop as interop_module
        if args.other_impl:
            interop_module.EXTERNAL_IMPL_PATH = args.other_impl
            if os.path.exists(args.other_impl):
                interop_module.SKIP_EXTERNAL_TESTS = False
                print(f"Using external implementation: {args.other_impl}")
            else:
                print(f"Warning: External implementation not found: {args.other_impl}")

        if args.category is None:
            args.category = ["interop"]
        elif "interop" not in args.category:
            args.category.append("interop")

    # Discover and load tests
    print("Discovering tests...")
    modules = discover_tests(
        categories=args.category,
        vectors_only=args.vectors_only
    )

    print(f"Loading {len(modules)} test module(s):")
    for m in modules:
        print(f"  - {m}")

    suite = load_tests(modules)
    print(f"Found {suite.countTestCases()} test(s)")
    print()

    # Run tests
    start_time = time.time()
    result = run_tests(suite, verbosity=verbosity)
    elapsed_time = time.time() - start_time

    # Print summary and return exit code
    return print_summary(result, elapsed_time)


if __name__ == "__main__":
    sys.exit(main())
