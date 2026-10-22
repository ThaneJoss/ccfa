const { test } = require('node:test');
const assert = require('node:assert/strict');
const catalog = require('../data/catalog.json');
const { create } = require('../src/matcher.js');
const matcher = create(catalog);

function item(fields, regular = true) {
  return {
    isRegularItem: () => regular,
    getField: name => fields[name] || '',
    setField() { throw new Error('Plugin must not edit metadata'); },
    save() { throw new Error('Plugin must not save items'); }
  };
}

test('complete 2026 catalog: 37 journals and 58 conferences, no duplicate labels', () => {
  assert.equal(catalog.venues.length, 95);
  assert.equal(catalog.venues.filter(v => v.type === 'journal').length, 37);
  assert.equal(new Set(catalog.venues.map(v => v.abbr)).size, 95);
  assert.equal(new Set(catalog.venues.map(v => v.category)).size, 10);
});

test('all source names survive case, Unicode width, punctuation and whitespace normalization', () => {
  for (const v of catalog.venues) {
    assert.equal(matcher.match(v.name), v.abbr, v.name);
    assert.equal(matcher.match('  ' + v.name.toUpperCase().replaceAll(' ', '  ') + '  '), v.abbr, v.name);
    assert.equal(matcher.match(v.abbr), v.abbr, v.abbr);
    for (const alias of v.aliases) assert.equal(matcher.match(alias), v.abbr, alias);
  }
});

const variants = [
  ['Proceedings of the AAAI Conference on Artificial Intelligence', 'AAAI'],
  ['2025 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)', 'CVPR'],
  ['Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition', 'CVPR'],
  ['Proceedings of the 38th International Conference on Machine Learning', 'ICML'],
  ['Advances in Neural Information Processing Systems', 'NeurIPS'],
  ['NIPS 2017', 'NeurIPS'],
  ['ＩＣＬＲ ２０２５', 'ICLR'],
  ['IEEE Transactions on Information Forensics and Security', 'TIFS'],
  ['IEEE Trans. Pattern Anal. Mach. Intell.', 'TPAMI'],
  ['IEEE/ACM Transactions on Networking', 'TON'],
  ['2024 USENIX Annual Technical Conference (USENIX ATC)', 'ACM SIGOPS ATC'],
  ['Proceedings of the ACM SIGKDD International Conference on Knowledge Discovery and Data Mining', 'SIGKDD'],
  ['Proceedings of the 2016 CHI Conference on Human Factors in Computing Systems', 'CHI'],
  ['IEEE Symposium on Security and Privacy (SP)', 'S&P'],
  ['Proceedings of the ACM Web Conference 2025', 'WWW'],
  ['IEEE Transactions on Multimedia', 'TMM'],
  ['Journal of Cryptology', 'J. Cryptol.']
];
for (const [input, expected] of variants) {
  test('venue variant: ' + input, () => assert.equal(matcher.match(input), expected));
}

test('non-A venues and acronym substrings remain blank', () => {
  for (const s of [
    'IJCAI', 'International Joint Conference on Artificial Intelligence',
    'ECCV', 'European Conference on Computer Vision', 'EMNLP',
    'Conference on Empirical Methods in Natural Language Processing',
    'SIGGRAPH Asia', 'ACM SIGGRAPH Asia Conference on Computer Graphics and Interactive Techniques',
    'IEEE Transactions on Cloud Computing', 'IEEE Access',
    'Real-Time Systems', 'International Conference on Supercomputing',
    'Computer Communications', 'Automated Software Engineering',
    'Machine Learning', 'Computer Supported Cooperative Work', 'World Wide Web',
    'IEEE Transactions on Artificial Intelligence',
    'International Conference on Machine Learning and Applications',
    'AAAI Conference on Artificial Intelligence and Interactive Digital Entertainment',
    'A survey of CVPR papers', 'Some SC papers', 'ICASSP', 'Unknown Journal', ''
  ]) assert.equal(matcher.match(s), '', s);
});

test('workshops, findings and companion tracks never inherit a main-conference label', () => {
  for (const s of [
    'CVPR Workshops', 'CVPRW', 'ICCVW', 'AAAI Workshop on Artificial Intelligence',
    'Findings of the Association for Computational Linguistics: ACL 2025',
    'Proceedings of the ACM Web Conference 2025 Companion',
    'CHI Extended Abstracts on Human Factors in Computing Systems',
    'Proceedings of the AAAI Conference on Artificial Intelligence: Technical Briefs',
    'International Conference on Learning Representations Workshops'
  ]) assert.equal(matcher.match(s), '', s);
});

test('item source fields are read without writing metadata', () => {
  assert.equal(matcher.forItem(item({ publicationTitle: variants[0][0] })), 'AAAI');
  assert.equal(matcher.forItem(item({ proceedingsTitle: variants[1][0] })), 'CVPR');
  assert.equal(matcher.forItem(item({ bookTitle: 'ICML 2025' })), 'ICML');
  assert.equal(matcher.forItem(item({ conferenceName: 'ICLR' })), 'ICLR');
  assert.equal(matcher.forItem(item({ journalAbbreviation: 'TPAMI' })), 'TPAMI');
});

test('mapped publicationTitle works even when type-specific fields are unavailable', () => {
  const mapped = item({});
  mapped.getField = (field, _unformatted, base) => {
    if (field === 'publicationTitle' && base === true) return variants[1][0];
    throw new Error('unsupported field');
  };
  assert.equal(matcher.forItem(mapped), 'CVPR');
});

test('titles, stale abbreviations, notes, attachments and deleted items cannot create false matches', () => {
  assert.equal(matcher.forItem(item({ title: 'CVPR' })), '');
  assert.equal(matcher.forItem(item({ publicationTitle: 'IEEE Access', journalAbbreviation: 'TPAMI' })), '');
  assert.equal(matcher.forItem(item({ publicationTitle: 'CVPR' }, false)), '');
  assert.equal(matcher.forItem({ ...item({ publicationTitle: 'CVPR' }), deleted: true }), '');
  assert.equal(matcher.forItem(null), '');
});

test('conflicting fields and workshop containers require metadata correction', () => {
  assert.equal(matcher.forItem(item({ publicationTitle: 'CVPR', conferenceName: 'ICML' })), '');
  assert.equal(matcher.forItem(item({ publicationTitle: 'CVPR Workshops', conferenceName: 'CVPR' })), '');
});

test('known workshop acronyms cannot inherit a parent conference from another field', () => {
  for (const [container, conference] of [
    ['CVPRW 2025', 'CVPR'],
    ['ICCVW', 'ICCV'],
    ['２０２５ ＣＶＰＲＷ', 'CVPR'],
    ['iccvw 2025', 'ICCV']
  ]) {
    assert.equal(matcher.forItem(item({ proceedingsTitle: container, conferenceName: conference })), '', container);
  }
});

test('edited item metadata is reflected immediately, without stale result caching', () => {
  const fields = { publicationTitle: 'CVPR' };
  const record = item(fields);
  assert.equal(matcher.forItem(record), 'CVPR');
  fields.publicationTitle = 'ICLR';
  assert.equal(matcher.forItem(record), 'ICLR');
});
