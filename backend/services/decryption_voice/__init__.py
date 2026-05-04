"""
Decryption Voice — Truth + Decryption layer for the post-game screen.

Two strictly separated generators:

    truth_line.generate_truth_line()  — 3-line headline (Coach Voice)
    decryption.generate_decryption()  — expansion text   (Decryption Voice)

The two generators MUST NOT see each other's output. They take different
inputs, follow different prompts, and produce different shapes. If the
voices blend, the Truth softens and the Decryption shortens — both fail.

Hard validators in `validators.py` enforce voice rules (word budget,
engine-word ban, why-it-worked check) at output time. Code-level
validation, not prompt-level — prompt discipline drifts.
"""
