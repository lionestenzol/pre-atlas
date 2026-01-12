"""
Quick test script to verify vectorization system is working.
Runs all components and reports status.
"""

import subprocess
import sqlite3
import sys
from pathlib import Path

def print_header(text):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")

def print_status(passed, message):
    icon = "✓" if passed else "✗"
    status = "PASS" if passed else "FAIL"
    print(f"{icon} [{status}] {message}")
    return passed

def check_dependencies():
    print_header("STEP 1: Checking Dependencies")

    try:
        import sentence_transformers
        print_status(True, "sentence-transformers installed")
    except ImportError:
        print_status(False, "sentence-transformers NOT installed")
        print("\n  Fix: pip install -r requirements.txt\n")
        return False

    try:
        import numpy
        print_status(True, "numpy installed")
    except ImportError:
        print_status(False, "numpy NOT installed")
        return False

    try:
        import sklearn
        print_status(True, "scikit-learn installed")
    except ImportError:
        print_status(False, "scikit-learn NOT installed")
        return False

    return True

def check_embeddings():
    print_header("STEP 2: Checking Embeddings")

    if not Path("results.db").exists():
        print_status(False, "results.db not found")
        print("\n  Fix: Run python init_results_db.py first\n")
        return False

    print_status(True, "results.db exists")

    con = sqlite3.connect("results.db")
    cur = con.cursor()

    # Check if embeddings table exists
    tables = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='embeddings'"
    ).fetchall()

    if not tables:
        print_status(False, "embeddings table not found")
        print("\n  Fix: Run python init_embeddings.py\n")
        con.close()
        return False

    print_status(True, "embeddings table exists")

    # Check row count
    count = cur.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    con.close()

    if count == 0:
        print_status(False, f"embeddings table is empty (0 rows)")
        print("\n  Fix: Run python init_embeddings.py\n")
        return False

    print_status(True, f"embeddings table has {count} rows")
    return True

def test_semantic_loops():
    print_header("STEP 3: Testing Semantic Loop Detection")

    try:
        result = subprocess.run(
            [sys.executable, "semantic_loops.py"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print_status(True, "semantic_loops.py executed successfully")

            if Path("semantic_loops.json").exists():
                print_status(True, "semantic_loops.json created")
                return True
            else:
                print_status(False, "semantic_loops.json not created")
                return False
        else:
            print_status(False, "semantic_loops.py failed")
            print(f"\nError: {result.stderr}\n")
            return False

    except subprocess.TimeoutExpired:
        print_status(False, "semantic_loops.py timed out (>30 seconds)")
        return False
    except Exception as e:
        print_status(False, f"Error running semantic_loops.py: {e}")
        return False

def test_search():
    print_header("STEP 4: Testing Semantic Search")

    try:
        result = subprocess.run(
            [sys.executable, "search_loops.py", "test query"],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            print_status(True, "search_loops.py executed successfully")

            if Path("search_results.json").exists():
                print_status(True, "search_results.json created")
                return True
            else:
                print_status(False, "search_results.json not created")
                return False
        else:
            print_status(False, "search_loops.py failed")
            print(f"\nError: {result.stderr}\n")
            return False

    except subprocess.TimeoutExpired:
        print_status(False, "search_loops.py timed out (>15 seconds)")
        return False
    except Exception as e:
        print_status(False, f"Error running search_loops.py: {e}")
        return False

def test_clustering():
    print_header("STEP 5: Testing Topic Clustering")

    try:
        result = subprocess.run(
            [sys.executable, "cluster_topics.py"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print_status(True, "cluster_topics.py executed successfully")

            if Path("topic_clusters.json").exists():
                print_status(True, "topic_clusters.json created")
                return True
            else:
                print_status(False, "topic_clusters.json not created")
                return False
        else:
            print_status(False, "cluster_topics.py failed")
            print(f"\nError: {result.stderr}\n")
            return False

    except subprocess.TimeoutExpired:
        print_status(False, "cluster_topics.py timed out (>30 seconds)")
        return False
    except Exception as e:
        print_status(False, f"Error running cluster_topics.py: {e}")
        return False

def main():
    print("\n" + "=" * 70)
    print("  VECTORIZATION SYSTEM TEST")
    print("=" * 70)

    results = []

    # Run all tests
    results.append(("Dependencies", check_dependencies()))

    if not results[-1][1]:
        print("\n⚠ Cannot continue without dependencies. Install and retry.\n")
        return False

    results.append(("Embeddings", check_embeddings()))

    if not results[-1][1]:
        print("\n⚠ Cannot continue without embeddings. Generate and retry.\n")
        return False

    results.append(("Semantic Loops", test_semantic_loops()))
    results.append(("Semantic Search", test_search()))
    results.append(("Topic Clustering", test_clustering()))

    # Summary
    print_header("TEST SUMMARY")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        print_status(result, name)

    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n✓ All tests passed! Vectorization system is working correctly.\n")
        print("Next steps:")
        print("  - Try: python search_loops.py 'your query'")
        print("  - View: semantic_loops.json")
        print("  - View: topic_clusters.json")
        print("  - Read: VECTORIZATION.md for full documentation\n")
        return True
    else:
        print("\n✗ Some tests failed. Check errors above.\n")
        print("Common fixes:")
        print("  - pip install -r requirements.txt")
        print("  - python init_embeddings.py")
        print("  - Check VECTORIZATION.md troubleshooting section\n")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
