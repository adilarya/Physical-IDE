"""
circuits.py - hardcoded reference circuits for the Physical IDE demo.

TODO: load these from Firestore / a content service post-hackathon.
"""
import copy

CIRCUITS = {
    "servo_control": {
        "name": "Servo Motor Control",
        "steps": [
            {
                "index": 1,
                "instruction": "Connect a red jumper wire from the Arduino 5V pin to the positive (+) power rail on the breadboard.",
                "success_criteria": "A red wire is connected between the Arduino and the breadboard power rail. No dangerous connections visible.",
                "danger_signals": ["wire connected to wrong rail", "short across power and ground"],
                "citation": "Arduino Uno R3 - power pins reference, p.2",
            },
            {
                "index": 2,
                "instruction": "Connect a black or brown jumper wire from the Arduino GND pin to the negative (-) power rail on the breadboard.",
                "success_criteria": "A black or brown wire is connected between the Arduino and the breadboard. Both a power wire and a ground wire are now present. No dangerous connections visible.",
                "danger_signals": ["ground wire on positive rail", "power and ground shorted together"],
                "citation": "Arduino Uno R3 - ground pins reference, p.2",
            },
            {
                "index": 3,
                "instruction": "Connect the servo: brown wire to the breadboard negative rail, red wire to the breadboard positive rail, yellow signal wire directly to Arduino pin 9.",
                "success_criteria": "A servo motor is connected to the circuit. The servo has three wires attached. Power rails are connected to the Arduino. No reversed polarity visible.",
                "danger_signals": ["servo red and brown wires swapped", "signal wire on power rail", "servo connected before power rails are set up"],
                "citation": "Servo motor wiring guide - SG90/MG90S pinout, p.1",
            },
        ],
    },
    # Original circuit kept for reference - requires LED and resistor
    "temperature_alarm": {
        "name": "Temperature Alarm (requires LED + resistor)",
        "steps": [
            {
                "index": 1,
                "instruction": "Connect a red wire from the 5V pin on the Arduino to the positive rail on the breadboard.",
                "expected_components": ["red_wire_5v_to_rail"],
                "success_criteria": "Red wire visible from Arduino 5V to breadboard + rail",
                "common_errors": ["wire_in_wrong_pin", "no_wire_detected"],
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


# Constraints the agent knows how to route around. Anything not in this set is
# silently ignored (the build proceeds with the unmodified circuit).
# TODO: extend with more substitutions (missing LED, missing jumper, etc.).
SUPPORTED_CONSTRAINTS = {"missing_220_resistor"}


def get_circuit_with_constraints(circuit_id, constraints):
    """Return a deep copy of a circuit, adapted for any user_constraints.

    This is the "Physical IDE" constraint-routing entrypoint: when a component
    is unavailable the agent reroutes the schematic instead of stalling the
    build. Call this once at session start and store the result.

    Args:
        circuit_id:  key into CIRCUITS (raises KeyError if unknown).
        constraints: list of constraint strings from the start_session event.
                     None or [] returns an unmodified circuit (still copied).

    Returns:
        A fresh deep copy the caller fully owns. This NEVER returns a reference
        into the global CIRCUITS dict, so the session may mutate it freely and
        repeated demo runs always start from clean ground truth.
    """
    # Deep copy FIRST: every edit below must touch the copy, never the global.
    circuit = copy.deepcopy(get_circuit(circuit_id))
    constraints = constraints or []

    # --- missing 220-ohm resistor  ->  substitute a 470-ohm -----------------
    # Higher resistance means less current: the LED is slightly dimmer but the
    # circuit stays safe. We locate the resistor step by content (not a fixed
    # index) so this keeps working if step order changes or a new circuit is
    # added that also uses a 220-ohm resistor.
    if "missing_220_resistor" in constraints:
        for step in circuit["steps"]:
            if "220-ohm" not in step["instruction"]:
                continue
            step["instruction"] = (
                step["instruction"].replace("220-ohm", "470-ohm")
                + " (Constraint reroute: 220-ohm resistor unavailable - "
                  "substituting 470-ohm. The LED will be slightly dimmer but "
                  "the circuit is safe.)"
            )
            step["expected_components"] = [
                c.replace("resistor_220", "resistor_470")
                for c in step["expected_components"]
            ]
            step["citation"] = step["citation"].replace("220 ohm", "470 ohm")

    return circuit
