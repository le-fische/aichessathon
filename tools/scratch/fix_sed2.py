with open("tools/test_acc_debug.py", "r") as f:
    text = f.read()
text = text.replace("""        if to == 6: # wks
            diffs[count, 0] = -1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 7; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 5; count+=1
        elif to == 2: # wqs
            diffs[count, 0] = -1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 0; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 3; count+=1
        elif to == 62: # bks
            diffs[count, 0] = -1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 63; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 61; count+=1
        elif to == 58: # bqs
            diffs[count, 0] = -1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 56; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 59; count+=1""", """        if to == 6: # wks
            diffs[count, 0] = -1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 7; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 5; count+=1
        elif to == 2: # wqs
            diffs[count, 0] = -1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 0; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 3; count+=1
        elif to == 62: # bks
            diffs[count, 0] = -1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 63; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 61; count+=1
        elif to == 58: # bqs
            diffs[count, 0] = -1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 56; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 59; count+=1""")
with open("tools/test_acc_debug.py", "w") as f:
    f.write(text)
