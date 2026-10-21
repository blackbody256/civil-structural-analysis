"""Final creep coefficient φ(∞, t0), BS EN 1992-1-1 Annex B.

The guide (Ch 5, 'Creep') points to the nomogram of EC2 Figure 3.1, which is a plot
of these expressions. The effective creep ratio is φef = φ(∞, t0)·M0Eqp/M0Ed.
"""
import math

CEMENT_ALPHA = {"S": -1, "N": 0, "R": 1}


def creep_coefficient(fcm, h0, rh, t0_days, cement="R"):
    t0 = max(0.5, t0_days * (9.0 / (2.0 + t0_days**1.2) + 1.0) ** CEMENT_ALPHA[cement])
    drying = (1.0 - rh / 100.0) / (0.1 * h0 ** (1.0 / 3.0))
    if fcm <= 35:
        phi_rh = 1.0 + drying
    else:
        phi_rh = (1.0 + drying * (35.0 / fcm) ** 0.7) * (35.0 / fcm) ** 0.2
    beta_fcm = 16.8 / math.sqrt(fcm)
    beta_t0 = 1.0 / (0.1 + t0**0.20)
    return phi_rh * beta_fcm * beta_t0


def effective_creep_ratio(fcm, h0, rh, t0_days, cement, moment_ratio):
    phi_inf = creep_coefficient(fcm, h0, rh, t0_days, cement)
    return {"phi_inf": phi_inf, "phi_ef": phi_inf * moment_ratio}
