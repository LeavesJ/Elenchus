from retnovation import content_loader


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
    assert "mechanism" in response  # sharper = a gap closed with a supplied mechanism
    assert "never grade the conclusion" in response
    # Intake classifies state without revealing labels to the student.
    assert "present_reasoned" in intake
    for p in (intake, push, response):
        assert p.strip()
