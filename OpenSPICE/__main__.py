from sys import argv
import struct
# from OpenSPICE import *

def spice_input(output_filename):
    # sp = SpiceParser(source=spice_txt)
    # print(sp)
    # dump raw file for op point sim
    print("--- LOLCATZ :: {} ---".format(output_filename))
    with open(output_filename, "w") as spice_raw_file:
        spice_raw_file_txt  = "Title: **.subckt rlc\n"
        spice_raw_file_txt += "Date: Thu Jun 11 23:17:40  2020\n"
        spice_raw_file_txt += "Plotname: Transient Analysis\n"
        spice_raw_file_txt += "Flags: real\n"
        spice_raw_file_txt += "No. Variables: 31\n"
        spice_raw_file_txt += "No. Points: 1\n"
        spice_raw_file_txt += "Variables:\n"
        spice_raw_file_txt += "\t0\ttime\ttime\n"
        spice_raw_file_txt += "\t1\tnode0\tvoltage\n"
        spice_raw_file_txt += "\t2\tnode1\tvoltage\n"
        spice_raw_file_txt += "\t3\tnode2\tvoltage\n"
        spice_raw_file_txt += "\t4\tnode3\tvoltage\n"
        spice_raw_file_txt += "\t5\tnode4\tvoltage\n"
        spice_raw_file_txt += "\t6\tnode5\tvoltage\n"
        spice_raw_file_txt += "\t7\tnode6\tvoltage\n"
        spice_raw_file_txt += "\t8\tnode7\tvoltage\n"
        spice_raw_file_txt += "\t9\tnode8\tvoltage\n"
        spice_raw_file_txt += "\t10\tnode9\tvoltage\n"
        spice_raw_file_txt += "\t11\tnode10\tvoltage\n"
        spice_raw_file_txt += "\t12\tnode11\tvoltage\n"
        spice_raw_file_txt += "\t13\tnode12\tvoltage\n"
        spice_raw_file_txt += "\t14\tnode13\tvoltage\n"
        spice_raw_file_txt += "\t15\ti(branch0)\tcurrent\n"
        spice_raw_file_txt += "\t16\ti(branch1)\tcurrent\n"
        spice_raw_file_txt += "\t17\ti(branch2)\tcurrent\n"
        spice_raw_file_txt += "\t18\ti(branch3)\tcurrent\n"
        spice_raw_file_txt += "\t19\ti(branch4)\tcurrent\n"
        spice_raw_file_txt += "\t20\ti(branch5)\tcurrent\n"
        spice_raw_file_txt += "\t21\ti(branch6)\tcurrent\n"
        spice_raw_file_txt += "\t22\ti(branch7)\tcurrent\n"
        spice_raw_file_txt += "\t23\ti(branch8)\tcurrent\n"
        spice_raw_file_txt += "\t24\ti(branch9)\tcurrent\n"
        spice_raw_file_txt += "\t25\ti(branch10)\tcurrent\n"
        spice_raw_file_txt += "\t26\ti(branch11)\tcurrent\n"
        spice_raw_file_txt += "\t27\ti(branch12)\tcurrent\n"
        spice_raw_file_txt += "\t28\ti(branch13)\tcurrent\n"
        spice_raw_file_txt += "\t29\ti(branch14)\tcurrent\n"
        spice_raw_file_txt += "\t30\ti(branch15)\tcurrent\n"
        spice_raw_file_txt += "Binary:\n"
        format_float = lambda x : hex(struct.unpack('<Q', struct.pack('<d', x))[0]).replace('0x', '')
        spice_raw_file_txt += ("{}".format(format_float(7.00)) * 31) + "\n"
        print(spice_raw_file_txt)
        spice_raw_file.write(spice_raw_file_txt)

print("argv[1] = {}, argv[2] = {}, argv[3] = {}".format(argv[1], argv[2], argv[3]))
with open(argv[1], "r") as txt:
    print("Reading from {}...".format(argv[1]))
    print("Writing to {}...".format(argv[3]))
    # spice_input(txt.read())
    spice_input(argv[3])
    print("Made it!")
