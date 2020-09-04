REG = "reg"
ORIG_DEF = "orig_def"
ORG_LIVE = "orig_live"
ROW_DEF = "row_def"
ROW_LIVE = "row_live"


class RegisterCache:
    def __init__(self):
        self.reg_cache = []  # [{reg, orig_def, orig_live, row_def, row_live}]

    def get_conflicting(self, reg, from_row):

        for i in reversed(self.reg_cache):
            if i[REG] == reg and (i[ROW_LIVE] is None or i[ROW_LIVE] > from_row):
                return i
        return None

    def get_reg_pending(self, reg, from_row):

        for i in self.reg_cache:
            if i[REG] == reg and (i[ROW_LIVE] is None or i[ROW_LIVE] >= from_row):
                return i
        return None

    def put_reg_wr(self, reg, orig_def, orig_live, row_def, row_live):
        for i in self.reg_cache:
            if i[REG] == reg and row_def == i[ROW_DEF] and orig_def == i[ORIG_DEF]:
                i[ROW_LIVE] = row_live
                return
        self.reg_cache.append({REG: reg,
                               ORIG_DEF: orig_def,
                               ORG_LIVE: orig_live,
                               ROW_DEF: row_def,
                               ROW_LIVE: row_live})

    def ch_reg_name(self, old_reg, new_reg, orig_def, row_def):
        for i in self.reg_cache:
            if i[REG] == old_reg and row_def == i[ROW_DEF] and orig_def == i[ORIG_DEF]:
                i[REG] = new_reg
                return

    def put_reg_rd(self, regs, row, orig_pos):
        for reg in regs:
            confl = self.get_reg_pending(reg, row)

            if confl is not None and confl[ORG_LIVE] == orig_pos:
                if confl[ROW_LIVE] is None:
                    confl[ROW_LIVE] = row


    def change_block(self, blck_end):
        new_cache = []
        for i in self.reg_cache:
            if i[ORG_LIVE] > blck_end:
                new_cache.append(i)

        self.reg_cache = new_cache

    def get_unavailable(self, from_row):
        unav = []
        for i in self.reg_cache:
            if (i[ROW_LIVE] is None or i[ROW_LIVE] > from_row) and i[REG] not in unav:
                unav.append(i["reg"])
        return unav
