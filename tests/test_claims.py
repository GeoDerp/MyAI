from myai.claims import Claim, label_claim_confidence, merge_claims


def test_label_claim_confidence():
    c = Claim(id='1', text='X causes Y', sources=[{'url': 'https://a.example/1'}])
    assert label_claim_confidence(c, high_threshold=2) == 'medium'

    c2 = Claim(id='2', text='X causes Y', sources=[{'url': 'https://a.example/1'}, {'url': 'https://b.example/2'}])
    assert label_claim_confidence(c2, high_threshold=2) == 'high'

    c3 = Claim(id='3', text='X causes Y', sources=[])
    assert label_claim_confidence(c3, high_threshold=2) == 'low'


def test_merge_claims():
    claims = [
        Claim(id='1', text='X causes Y', sources=[{'url': 'https://a.example/1'}]),
        Claim(id='2', text='x causes y', sources=[{'url': 'https://b.example/2'}]),
        Claim(id='3', text='Other claim', sources=[{'url': 'https://c.example/3'}]),
    ]
    merged = merge_claims(claims, min_sources_for_high=2)
    # Expect two merged claims
    texts = {m['text'].lower(): m for m in merged}
    assert 'x causes y' in texts
    assert texts['x causes y']['corroboration'] >= 2
    assert texts['x causes y']['label'] == 'high'
    assert 'other claim' in texts


def test_semantic_merge_similar_texts():
    claims = [
        Claim(id='1', text='Smoking increases lung cancer risk', sources=[{'url': 'https://a.example/1'}]),
        Claim(id='2', text='Tobacco smoking raises risk of lung cancer', sources=[{'url': 'https://b.example/2'}]),
        Claim(id='3', text='Unrelated claim', sources=[{'url': 'https://c.example/3'}]),
    ]
    merged = merge_claims(claims, min_sources_for_high=2)
    texts = [m['text'].lower() for m in merged]
    # Expect the two smoking claims to be merged into a single entry
    matched = [t for t in texts if 'smoking' in t or 'tobacco' in t]
    assert len(matched) == 1


def test_contradictory_but_lexically_similar_not_merged():
    claims = [
        Claim(id='1', text='Vaccines cause autism', sources=[{'url': 'https://a.example/1'}]),
        Claim(id='2', text='Vaccines do not cause autism', sources=[{'url': 'https://b.example/2'}]),
    ]
    merged = merge_claims(claims, min_sources_for_high=2)
    # Should not merge contradictory claims despite lexical similarity
    assert len(merged) == 2
