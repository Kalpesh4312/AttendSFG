"""
Facial recognition matching helpers.

Face DETECTION and DESCRIPTOR EXTRACTION happen entirely in the browser via
face-api.js (TensorFlow.js), which returns a 128-dimensional embedding
("descriptor") that uniquely represents a detected face. The server never
sees raw images for verification -- only these numeric descriptors -- which
keeps the backend lightweight and avoids shipping heavy native CV
dependencies.

This module only performs the final comparison: Euclidean distance between
the descriptor captured at enrollment and the one captured at attendance
time. A smaller distance means a closer match.
"""
import numpy as np


def euclidean_distance(descriptor_a, descriptor_b):
    a = np.array(descriptor_a, dtype=np.float64)
    b = np.array(descriptor_b, dtype=np.float64)
    if a.shape != b.shape:
        raise ValueError("Descriptor length mismatch")
    return float(np.linalg.norm(a - b))


def is_face_match(stored_descriptor, live_descriptor, threshold):
    distance = euclidean_distance(stored_descriptor, live_descriptor)
    return distance <= threshold, distance


def validate_descriptor(descriptor, expected_length):
    return (
        isinstance(descriptor, list)
        and len(descriptor) == expected_length
        and all(isinstance(x, (int, float)) for x in descriptor)
    )
