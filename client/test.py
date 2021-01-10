import os
source = "C:\\Keil"
new_root = "C:\\test\\"
for root, dirs, files in os.walk(source, topdown=False):
    new_root = os.path.join(new_root, root.replace(source + "\\", ""))
    if not os.path.exists(new_root):
        os.makedirs(new_root)
    for dir in dirs:
        new_dir = os.path.join(new_root, dir)
        if not os.path.exists(new_dir):
            os.makedirs(root)
    for file in files:
        old_file = os.path.join(root, file)
        new_file = os.path.join(new_root, file)
        if not os.path.exists(new_file):

            with open(old_file, "br") as s_fp:
                with open(new_file, "bw+") as t_fp:
                    source_data = s_fp.read()
                    while source_data:
                        t_fp.write(source_data)
                        source_data = s_fp.read()

    # new_root = "C:\\test\\"
    # for name in dirs:
    #     new = os.path.join(new_root, root.replace(source, ""))
    #     print(new)
    #     if not os.path.exists(new):
    #         os.makedirs(new)

    # for name in files:
    #     print(os.path.join(root, name))

        # if not os.path.exists(new_root):
        #     os.makedirs(new_root)
        #     print(new_root)

# for root, dirs, files in os.walk(r, topdown=False):
#     old_root = root
#     new_root = "C:\\test" + root.replace(r, "")
