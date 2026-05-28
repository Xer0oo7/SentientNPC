import json

from database import DialogueLog, Memory, NPC, Quest, Relationship, SessionLocal, init_db


NPCS = [
    {
        "id": "guard_01",
        "name": "Guard",
        "personality": {
            "aggressive": 80,
            "friendly": 20,
            "greedy": 0,
            "bravery": 90,
            "curiosity": 30,
            "loyalty": 60,
        },
        "emotion": "neutral",
        "reputation": 0,
        "relationship": -10,
        "memories": [
            ("player_said_hello", "Player greeted the guard at the town gate.", "town_gate", 0.1),
            ("player_stole", "Player was seen taking apples from a market crate.", "market_district", 0.8),
            ("player_helped_npc", "Player helped repair a broken watch post lantern.", "watch_post", 0.6),
        ],
    },
    {
        "id": "merchant_01",
        "name": "Merchant",
        "personality": {
            "aggressive": 15,
            "friendly": 60,
            "greedy": 70,
            "bravery": 30,
            "curiosity": 50,
            "loyalty": 25,
        },
        "emotion": "happy",
        "reputation": 20,
        "relationship": 35,
        "memories": [
            ("player_completed_quest", "Player delivered a missing shipment safely.", "market_stall", 0.6),
            ("give_gift", "Player gave the merchant a polished silver ring.", "bazaar", 0.5),
            ("player_stole", "Player lingered near the coin box during a busy trade hour.", "market_stall", 0.75),
        ],
    },
    {
        "id": "elder_01",
        "name": "Elder",
        "personality": {
            "aggressive": 10,
            "friendly": 90,
            "greedy": 5,
            "bravery": 45,
            "curiosity": 70,
            "loyalty": 85,
        },
        "emotion": "neutral",
        "reputation": 50,
        "relationship": 65,
        "memories": [
            ("player_said_hello", "Player respectfully greeted the elder near the shrine.", "village_shrine", 0.2),
            ("player_helped_npc", "Player gathered herbs for the elder's remedy.", "forest_edge", 0.7),
            ("player_completed_quest", "Player restored a lost family relic to the elder.", "elder_home", 0.9),
        ],
    },
]


def seed():
    init_db()
    db = SessionLocal()
    try:
        db.query(DialogueLog).delete()
        db.query(Memory).delete()
        db.query(Relationship).delete()
        db.query(Quest).delete()
        db.query(NPC).delete()

        for item in NPCS:
            npc = NPC(
                id=item["id"],
                name=item["name"],
                personality=json.dumps(item["personality"]),
                emotion=item["emotion"],
                reputation=item["reputation"],
            )
            db.add(npc)
            for event_type, description, location, importance in item["memories"]:
                db.add(
                    Memory(
                        npc_id=item["id"],
                        event_type=event_type,
                        description=description,
                        location=location,
                        importance=importance,
                        is_longterm=importance >= 0.7,
                    )
                )
            db.add(
                Relationship(
                    npc_id=item["id"],
                    player_id="player_001",
                    score=item["relationship"],
                )
            )

        db.commit()
        print("Seed complete: 3 NPCs, 9 memories, and 3 relationships created.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
