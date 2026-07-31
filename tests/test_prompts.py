from elenchus import content_loader


def test_load_prompt_reads_named_template(tmp_path):
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "intake.md").write_text("CLASSIFY THE OPENING")
    assert content_loader.load_prompt("intake", root=tmp_path) == "CLASSIFY THE OPENING"


def test_real_prompts_encode_disband_rules():
    intake = content_loader.load_prompt("intake").lower()
    push = content_loader.load_prompt("push").lower()
    response = content_loader.load_prompt("response").lower()
    # Doctrine must live in the prompts (gate doctrine in content, not code).
    assert "never name the frame" in push
    assert "never hand the answer" in push
    assert "never adopt or confirm a label the student used" in push
    assert "mechanism" in response  # sharper = a gap closed with a supplied mechanism
    assert "never grade the conclusion" in response
    # push_stress.md's own new line ("What they already argued on this angle is in the 'argued
    # on THIS angle' block above") is deliberately NOT pinned here. It claims the stress author
    # receives the student's positions; the controller proved that false by enumerating 156
    # generate_push calls (24 with stress=True), zero of which carried a position on either
    # field, because stress only fires on the FIRST selection of a rubric's decision frame, when
    # the trajectory is empty. Pinning it would make this suite defend a claim the wiring
    # contradicts. See .superpowers/sdd/rework-5-report.md (R5, 5d).
    # Intake classifies state without revealing labels to the student.
    assert "present_reasoned" in intake
    for p in (intake, push, response):
        assert p.strip()
