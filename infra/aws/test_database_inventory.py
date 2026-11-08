import unittest
from schema_validation import normalize_literal_array_casts,comparable


class ExactArrayCastNormalization(unittest.TestCase):
    def test_only_documented_literal_array_cast_distribution(self):
        source="CHECK (status = ANY ((ARRAY['a'::character varying, 'b'::character varying])::text[]))"
        target="CHECK (status = ANY (ARRAY[('a'::character varying)::text, ('b'::character varying)::text]))"
        self.assertEqual(normalize_literal_array_casts(source),target)
    def test_changed_values_and_operators_still_differ(self):
        source="CHECK (amount > 0 AND status=ANY ((ARRAY['a'::character varying])::text[]))"
        different="CHECK (amount >= 0 AND status=ANY (ARRAY[('a'::character varying)::text]))"
        self.assertNotEqual(normalize_literal_array_casts(source),normalize_literal_array_casts(different))
        self.assertNotEqual(normalize_literal_array_casts(source),normalize_literal_array_casts(source.replace("'a'","'b'")))
    def test_embedded_sql_string_is_never_rewritten(self):
        value="CHECK (value <> '(ARRAY[''a''::character varying])::text[]')"
        self.assertEqual(normalize_literal_array_casts(value),value)
    def test_unrelated_cast_unchanged(self):
        value="CHECK (value=ANY ((ARRAY['1'::character varying])::integer[]))"
        self.assertEqual(normalize_literal_array_casts(value),value)
    def test_counts_and_sequence_changes_are_not_hidden(self):
        source={'rows':{'table':10},'sequences':{'s':[10,True]},'constraints':[],'indexes':[]}
        target={**source,'rows':{'table':9}}
        self.assertNotEqual(comparable(source),comparable(target))
        target={**source,'sequences':{'s':[9,True]}}
        self.assertNotEqual(comparable(source),comparable(target))


if __name__=='__main__':unittest.main()
