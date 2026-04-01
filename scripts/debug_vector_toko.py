"""
Debug vector search toko.
Jalankan: python scripts/debug_vector_toko.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from app.services.vector import search_toko


async def main():
    queries = [
        "restu jaya motor banjarsari",
        "restu jaya motor kragilan kadipiro surakarta banjarsari",
        "restu jaya motor surakarta",
        "RESTU JAYA MOTOR BANJARSARI SURAKARTA",
    ]

    for query in queries:
        print(f"\nQuery: '{query}'")
        results = await search_toko(query, limit=200)

        # Cek apakah toko ID 184452 ada di hasil
        found = [r for r in results if str(r["toko_id"]) == "184452"]
        print(f"Total hasil: {len(results)}")
        print(f"Toko 184452 ditemukan: {'YA' if found else 'TIDAK'}")

        if found:
            print(f"  Posisi: {next(i+1 for i,r in enumerate(results) if str(r['toko_id'])=='184452')}")
            print(f"  Similarity: {found[0]['similarity']}")

        # Filter simulasi executor
        alamat_words = query.lower().split()
        filtered = [
            r for r in results
            if any(w in r["address"].lower() for w in alamat_words)
        ]
        found_in_filtered = [r for r in filtered if str(r["toko_id"]) == "184452"]
        print(f"Setelah filter kata alamat: {len(filtered)} hasil")
        print(f"Toko 184452 ada di filtered: {'YA' if found_in_filtered else 'TIDAK'}")

        if results:
            print(f"Top 3 hasil:")
            for r in results[:3]:
                print(f"  [{r['toko_id']}] {r['name']} — {r['address']} (sim: {r['similarity']})")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
