#!/usr/bin/env python3

from datetime import datetime
from array    import array

def gen_out_txt(raw_fname, title, test_type, soln, sorted_nodes):
    spice_raw_file_txt  = "Title: {}\n".format(title)
    spice_raw_file_txt += "Date: {}\n".format(datetime.today().strftime('%c'))
    spice_raw_file_txt += "Plotname: {}\n".format("Transient Analysis" if test_type == "tran" else "Operating Point")
    spice_raw_file_txt += "Flags: {}\n".format("real")
    spice_raw_file_txt += "No. Variables: {}\n".format(len(soln[0]))
    spice_raw_file_txt += "No. Points: {}\n".format(len(soln))
    spice_raw_file_txt += "Variables:\n"
    spice_raw_file_txt += "\t0\ttime\ttime\n"
    spice_raw_file_txt += "".join(["\t{}\t{}\tvoltage\n".format(1+i,v) for i,v in enumerate(sorted_nodes)])
    spice_raw_file_txt += "".join(["\t{}\t{}\tcurrent\n".format(1+len(sorted_nodes)+i,i) for i in range(len(soln[0])-len(sorted_nodes))])
    spice_raw_file_txt += "Binary:\n"
    with open(raw_fname, "w") as spice_raw_file:
        spice_raw_file.write(spice_raw_file_txt)
    with open(raw_fname, "ab") as spice_raw_file:
        [spice_raw_file.write(array('d', s).tobytes()) for s in soln]
