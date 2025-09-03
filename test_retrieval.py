#!/usr/bin/env python3
"""
Simple test script to demonstrate retrieval pipeline functionality
"""
import requests
import json
import time

def test_health_check():
    """Test if the API is responsive"""
    try:
        response = requests.get("http://localhost:8000/api/v1/health", timeout=5)
        print(f"✅ Health Check: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health Check Failed: {e}")
        return False

def test_search_api():
    """Test the search API endpoint"""
    queries = [
        "test",
        "climate change", 
        "technology innovation",
        "economic policy"
    ]
    
    for query in queries:
        print(f"\n🔍 Testing search for: '{query}'")
        try:
            start_time = time.time()
            response = requests.get(
                f"http://localhost:8000/api/search?q={query}", 
                timeout=30
            )
            latency = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Status: {response.status_code}")
                print(f"⏱️  Latency: {latency:.1f}ms")
                print(f"📊 Results: {len(data.get('results', []))}")
                
                # Show first result if available
                results = data.get('results', [])
                if results:
                    first = results[0]
                    print(f"🎯 Top Result:")
                    print(f"   Title: {first.get('title', 'N/A')}")
                    print(f"   Score: {first.get('score', 0):.3f}")
                    print(f"   Rerank Score: {first.get('rerank_score', 0):.3f}")
                    print(f"   Content: {first.get('content', '')[:100]}...")
                else:
                    print("   No results found (expected if no data ingested)")
            else:
                print(f"❌ Status: {response.status_code}")
                print(f"   Error: {response.text}")
                
        except Exception as e:
            print(f"❌ Search failed: {e}")

def test_metrics():
    """Test the metrics endpoint"""
    try:
        response = requests.get("http://localhost:8000/metrics", timeout=5)
        print(f"\n📊 Metrics endpoint: {response.status_code}")
        if response.status_code == 200:
            metrics = response.text
            # Look for retrieval metrics
            retrieval_metrics = [line for line in metrics.split('\n') 
                               if 'retrieval' in line and not line.startswith('#')]
            if retrieval_metrics:
                print("🎯 Retrieval metrics found:")
                for metric in retrieval_metrics[:5]:  # Show first 5
                    print(f"   {metric}")
            else:
                print("   No retrieval metrics yet (run searches first)")
    except Exception as e:
        print(f"❌ Metrics failed: {e}")

if __name__ == "__main__":
    print("🚀 Barta Retrieval Pipeline Test")
    print("=" * 40)
    
    # Test health first
    if not test_health_check():
        print("❌ API not ready, exiting...")
        exit(1)
    
    # Test search functionality
    test_search_api()
    
    # Test metrics
    test_metrics()
    
    print("\n✅ Test completed!")