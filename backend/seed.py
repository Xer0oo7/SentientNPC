import json

from database import DialogueLog, Memory, NPC, Quest, Relationship, SimulationEvent, SessionLocal, init_db
from fsm import derive_initial_state


NPCS = [
    {
        "id": "guard_01",
        "name": "Aldric",
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
        "pos_x": -30.0,
        "pos_z": 30.0,
        "facing_angle": 90.0,
        "zone": "guard_post",
        "vision_range": 25.0,
        "vision_fov": 140.0,
        "hearing_range": 35.0,
        "memories": [
            ("player_said_hello", "Player greeted the guard at the town gate.", "guard_post", 0.1),
            ("player_stole", "Player was seen taking apples from a market crate.", "market_stall", 0.8),
            ("player_helped_npc", "Player helped repair a broken watch post lantern.", "guard_post", 0.6),
        ],
    },
    {
        "id": "merchant_01",
        "name": "Hilda",
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
        "pos_x": 30.0,
        "pos_z": 30.0,
        "facing_angle": 270.0,
        "zone": "market_stall",
        "vision_range": 15.0,
        "vision_fov": 120.0,
        "hearing_range": 25.0,
        "memories": [
            ("player_completed_quest", "Player delivered a missing shipment safely.", "market_stall", 0.6),
            ("give_gift", "Player gave the merchant a polished silver ring.", "market_stall", 0.5),
            ("player_stole", "Player lingered near the coin box during a busy trade hour.", "market_stall", 0.75),
        ],
    },
    {
        "id": "elder_01",
        "name": "Elder Morvyn",
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
        "pos_x": 0.0,
        "pos_z": 5.0,
        "facing_angle": 0.0,
        "zone": "town_square",
        "vision_range": 15.0,
        "vision_fov": 100.0,
        "hearing_range": 20.0,
        "memories": [
            ("player_said_hello", "Player respectfully greeted the elder near the shrine.", "town_square", 0.2),
            ("player_helped_npc", "Player gathered herbs for the elder's remedy.", "town_square", 0.7),
            ("player_completed_quest", "Player restored a lost family relic to the elder.", "town_square", 0.9),
        ],
    },
    {
        "id": "blacksmith_01",
        "name": "Tormund",
        "personality": {
            "aggressive": 40,
            "friendly": 50,
            "greedy": 20,
            "bravery": 75,
            "curiosity": 35,
            "loyalty": 90,
        },
        "emotion": "neutral",
        "reputation": 10,
        "relationship": 15,
        "pos_x": 0.0,
        "pos_z": -50.0,
        "facing_angle": 0.0,
        "zone": "smithy",
        "vision_range": 18.0,
        "vision_fov": 120.0,
        "hearing_range": 20.0,
        "memories": [
            ("player_said_hello", "Player asked Tormund about forging techniques.", "smithy", 0.2),
            ("give_gift", "Player brought rare iron ore from the northern mines.", "smithy", 0.6),
        ],
    },
    {
        "id": "innkeeper_01",
        "name": "Berta",
        "personality": {
            "aggressive": 10,
            "friendly": 85,
            "greedy": 45,
            "bravery": 25,
            "curiosity": 60,
            "loyalty": 55,
        },
        "emotion": "happy",
        "reputation": 15,
        "relationship": 40,
        "pos_x": -30.0,
        "pos_z": -30.0,
        "facing_angle": 45.0,
        "zone": "tavern",
        "vision_range": 12.0,
        "vision_fov": 110.0,
        "hearing_range": 25.0,
        "memories": [
            ("player_said_hello", "Player ordered a mead and complimented the tavern.", "tavern", 0.15),
            ("player_helped_npc", "Player carried supplies from the market to the tavern.", "tavern", 0.55),
        ],
    },
    {
        "id": "beggar_01",
        "name": "Pip",
        "personality": {
            "aggressive": 20,
            "friendly": 40,
            "greedy": 55,
            "bravery": 15,
            "curiosity": 85,
            "loyalty": 10,
        },
        "emotion": "sad",
        "reputation": -15,
        "relationship": 5,
        "pos_x": 5.0,
        "pos_z": 0.0,
        "facing_angle": 180.0,
        "zone": "town_square",
        "vision_range": 20.0,
        "vision_fov": 160.0,
        "hearing_range": 35.0,
        "memories": [
            ("give_gift", "Player gave Pip a loaf of bread.", "town_square", 0.5),
            ("player_stole", "Player snatched coins from the fountain.", "town_square", 0.65),
        ],
    },
    {
        "id": "priest_01",
        "name": "Father Aldwin",
        "personality": {
            "aggressive": 5,
            "friendly": 95,
            "greedy": 5,
            "bravery": 55,
            "curiosity": 60,
            "loyalty": 80,
        },
        "emotion": "neutral",
        "reputation": 40,
        "relationship": 50,
        "pos_x": 30.0,
        "pos_z": -30.0,
        "facing_angle": 315.0,
        "zone": "church",
        "vision_range": 15.0,
        "vision_fov": 100.0,
        "hearing_range": 25.0,
        "memories": [
            ("player_said_hello", "Player knelt and prayed alongside Father Aldwin.", "church", 0.3),
            ("player_helped_npc", "Player donated supplies to the church orphanage.", "church", 0.7),
        ],
    },
]

# Player entity placed at town square
PLAYER = {
    "id": "player_001",
    "pos_x": 0.0,
    "pos_z": 0.0,
    "facing_angle": 0.0,
    "zone": "town_square",
}


def seed():
    init_db()
    db = SessionLocal()
    try:
        # Clear all existing data
        db.query(SimulationEvent).delete()
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
                fsm_state=derive_initial_state(item["zone"], item["emotion"]),
                reputation=item["reputation"],
                pos_x=item["pos_x"],
                pos_z=item["pos_z"],
                facing_angle=item["facing_angle"],
                zone=item["zone"],
                vision_range=item.get("vision_range", 20.0),
                vision_fov=item.get("vision_fov", 120.0),
                hearing_range=item.get("hearing_range", 30.0),
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
    finally:
        db.close()


if __name__ == "__main__":
    seed()
