from threads_ops import persona


def test_build_persona_prompt_includes_experience_and_supplement():
    prompt = persona.build_persona_prompt(experience="テスト体験", supplement="補足メモ")

    assert "テスト体験" in prompt
    assert "補足メモ" in prompt
    assert "共感のフック" in prompt


def test_save_and_load_persona_round_trips(tmp_dirs):
    path = tmp_dirs["persona_file"]

    assert persona.load_persona(path) is None

    saved_path = persona.save_persona("ペルソナ本文", path=path)

    assert saved_path == str(path)
    assert persona.load_persona(path) == "ペルソナ本文"
