"""
circuits.py - hardcoded reference circuits for the Physical IDE demo.

TODO: load these from Firestore / a content service post-hackathon.
"""

CIRCUITS = {
    "temperature_alarm": {
        "name": "Temperature Alarm",
        "steps": [
            {
                "index": 1,
                "instruction": "Connect a red wire from the 5V pin on the Arduino to the positive rail on the breadboard.",
                "expected_components": ["red_wire_5v_to_rail"],
                "success_criteria": "Red wire visible from Arduino 5V to breadboard + rail",
                "common_errors": ["wire_in_wrong_pin", "no_wire_detected"],
                # citation is surfaced in the downstream payload; added beyond the
                # base spec so the locked contract's `citation` field is populated.
                "citation": "Arduino Uno R3 - power pins reference, p.2",
            },
            {
                "index": 2,
                "instruction": "Place the LED on the breadboard, longer leg in row 10, shorter leg in row 11.",
                "expected_components": ["led_at_row_10_11"],
                "success_criteria": "LED with anode in row 10, cathode in row 11",
                "common_errors": ["led_reversed", "led_short_circuit_to_ground"],
                "citation": "LED polarity guide - anode vs cathode, p.1",
            },
            {
                "index": 3,
                "instruction": "Connect a 220-ohm resistor from row 11 to the ground rail.",
                "expected_components": ["resistor_220_row_11_to_gnd"],
                "success_criteria": "Resistor bridging row 11 and GND rail",
                "common_errors": ["wrong_resistor_value", "resistor_misplaced"],
                "citation": "Resistor color codes - 220 ohm band reference, p.4",
            },
        ],
    },
}


def get_circuit(circuit_id):
    circuit = CIRCUITS.get(circuit_id)
    if circuit is None:
        raise KeyError(f"unknown circuit_id: {circuit_id}")
    return circuit


def step_count(circuit_id):
    return len(get_circuit(circuit_id)["steps"])


def get_step(circuit_id, index):
    """1-based step lookup. Returns None when the index is out of range."""
    steps = get_circuit(circuit_id)["steps"]
    if 1 <= index <= len(steps):
        return steps[index - 1]
    return None
