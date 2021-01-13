import os
# source = "/Users/lishaoxu/Desktop/tools"
# new_root = "/Users/lishaoxu/Desktop/tools1"
# for root, dirs, files in os.walk(source, topdown=False):
#     cur_path = root.replace(source, "")
#     if cur_path:
#         if cur_path[0] in ["/", "\\"]:
#             cur_path = cur_path[1:]
#     else:
#         cur_path = ""
#     tep_new_root = os.path.join(new_root, cur_path)
#     if not os.path.exists(tep_new_root):
#         os.makedirs(tep_new_root)
#     for dir in dirs:
#         new_dir = os.path.join(tep_new_root, dir)
#         if not os.path.exists(new_dir):
#             os.makedirs(new_dir)
#     for file in files:
#         old_file = os.path.join(root, file)
#         new_file = os.path.join(tep_new_root, file)
#         if not os.path.exists(new_file):
#
#             with open(old_file, "br") as s_fp:
#                 with open(new_file, "bw+") as t_fp:
#                     source_data = s_fp.read()
#                     while source_data:
#                         t_fp.write(source_data)
#                         source_data = s_fp.read()

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


def before_to_next(in_path, windows=True):
    try:
        t_root = str()
        t_path = str()
        if windows:
            if not os.path.exists(in_path):
                return None, None
            base_root = in_path.split(":")
            if not len(base_root) > 1:
                return None, None
            t_root = base_root[0] + ":"
            base_path = in_path.replace(t_root, "")
            t_path = str()
            if base_path:
                t_path = base_path[1:]
        else:
            if not os.path.exists(in_path):
                return None, None
            base_root = in_path.split("/")
            t_root = base_root[1]
            if t_root != "Users":
                return None, None
            replace_str = "/" + t_root
            if len(base_root) > 2:
                replace_str += "/"
            t_path = in_path.replace(replace_str, "")
        return t_root, t_path
    except Exception:
        return None, None

# r = before_to_next("C:\\")
r = before_to_next("/Users/lishaoxu/", False)
print(r)

# assert r == ("C:", "Users")
# assert r == ("C:", "")
assert r == ("Users", "lishaoxu/")
# assert r == (None, None)