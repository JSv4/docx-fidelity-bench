import copy
from pathlib import Path
import tempfile
import unittest
from bench import common, runner, word_fonts
from test_contract import case, result


class SeparateReferenceAndLayoutTracks(unittest.TestCase):
    def test_provider_tracks_cannot_be_compared_even_if_other_fields_match(self):
        before = result([case('sample', 'paragraphs')])
        after = copy.deepcopy(before)
        before['track'] = 'word'
        after['track'] = 'libreoffice'
        with self.assertRaisesRegex(ValueError, 'provider track'):
            runner.compare(before, after, 0)

    def test_layout_profiles_cannot_reuse_each_others_baseline(self):
        before = result([case('sample', 'paragraphs')])
        after = copy.deepcopy(before)
        after['contract']['layoutProfile'] = 'word'
        after['contractDigest'] = common.identity(after['contract'])
        with self.assertRaisesRegex(ValueError, 'layout profile'):
            runner.compare(before, after, 0)

    def test_older_implicit_default_layout_is_the_same_as_explicit_default(self):
        before = result([case('sample', 'paragraphs')])
        after = copy.deepcopy(before)
        after['contract']['layoutProfile'] = 'default'
        after['contractDigest'] = common.identity(after['contract'])
        self.assertEqual(runner.compare(before, after, 0), [])

    def test_an_explicit_empty_manifest_does_not_fall_back_to_another_corpus(self):
        with self.assertRaises(ValueError):
            common.validate_registry({})

    def test_invalid_layout_profile_identity_is_rejected(self):
        record = result([case('sample', 'paragraphs')])
        record['contract']['layoutProfile'] = None
        record['contractDigest'] = common.identity(record['contract'])
        with self.assertRaisesRegex(ValueError, 'layout profile identity'):
            runner.validate_result(record)


class WordCaptureBundleIntegrity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        native = self.root / 'native.pdf'
        native.write_bytes(b'Exact reviewed PDF; font inspection tested separately')
        self.registry = {'cases': [{'id': 'sample', 'sha256': 'a' * 64}]}
        self.env = {'contract': {'fonts': {'font.ttf': {'sha256': 'b' * 64}}}}
        capture = {'track': 'word-online', 'rightsApproved': True,
                   'profile': {'review': 'final', 'comments': 'hidden'},
                   'fontContract': self.env['contract']['fonts'],
                   'fontIdentityBindings': {'sample': [{'reviewedGlyphIdentity': True}]},
                   'cases': {'sample': {'inputSha256': 'a' * 64, 'pdfSha256': common.digest(native)}}}
        self.bundle = {'schema': 1, 'track': 'word-online', 'capture': capture,
                       'suiteDigest': common.identity(self.registry), 'environment': self.env['contract'],
                       'fontIdentityInspectorVersion': word_fonts.VERSION,
                       'fontIdentityInspectorSha256': common.digest(Path(word_fonts.__file__)),
                       'cases': {'sample': dict(capture['cases']['sample'], pdf='native.pdf')}}

    def validate(self):
        runner.validate_bundle(self.bundle, self.root, self.registry, self.env)

    def test_matching_bundle_preserves_capture_binding(self):
        self.validate()

    def test_changed_verifier_does_not_reuse_registered_qualification(self):
        self.bundle['fontIdentityInspectorSha256'] = 'c' * 64
        with self.assertRaisesRegex(ValueError, 'verifier changed'):
            self.validate()

    def test_bindings_cannot_be_relabeled_as_libreoffice(self):
        self.bundle['track'] = 'libreoffice'
        with self.assertRaisesRegex(ValueError, 'verifier changed'):
            self.validate()

    def test_unapproved_rights_or_changed_view_blocks_binding(self):
        for key, value in [('rightsApproved', False), ('profile', {'review': 'original', 'comments': 'hidden'})]:
            with self.subTest(key=key):
                original = self.bundle['capture'][key]
                self.bundle['capture'][key] = value
                with self.assertRaisesRegex(ValueError, 'unverified'):
                    self.validate()
                self.bundle['capture'][key] = original

    def test_orphan_binding_or_inspector_evidence_is_rejected(self):
        self.bundle['capture']['fontIdentityBindings']['unknown'] = []
        with self.assertRaisesRegex(ValueError, 'exact registered capture cases'):
            self.validate()
        self.bundle['capture']['fontIdentityBindings'] = {}
        with self.assertRaisesRegex(ValueError, 'lacks its capture bindings'):
            self.validate()

    def test_capture_digest_cannot_change_behind_registered_entry(self):
        for key in ('inputSha256', 'pdfSha256'):
            with self.subTest(key=key):
                original = self.bundle['capture']['cases']['sample'][key]
                self.bundle['capture']['cases']['sample'][key] = 'c' * 64
                with self.assertRaisesRegex(ValueError, 'capture digests changed'):
                    self.validate()
                self.bundle['capture']['cases']['sample'][key] = original

    def test_binding_map_cannot_be_a_list(self):
        self.bundle['capture']['fontIdentityBindings'] = []
        with self.assertRaisesRegex(ValueError, 'exact registered capture cases'):
            self.validate()
