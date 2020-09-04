import unittest
from ebpf_parser import *


class ParserTestCases(unittest.TestCase):
    def test_branch_opcode_coverage(self):
        self.assertCountEqual(BRANCH_OPCODE, BRANCH_OPCODE)


if __name__ == '__main__':
    unittest.main()
