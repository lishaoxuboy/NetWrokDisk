import configparser


class Config:


    def __init__(self):
        self.Config_Parser = configparser.ConfigParser()
        self.Config_Parser.read('/Users/lishaoxu/MySoft/NetWrokDisk/client/static/config.ini', encoding="utf-8")
        # self.Config_Parser.read('static/config.ini', encoding="utf-8")
        self._get_all_config()

    def get_conf(self, key, v_type, default=str()):
        if v_type is str:
            try:
                r = self.Config_Parser.get("main", key)
                return r
            except Exception:
                return default
        else:
            try:
                r = self.Config_Parser.getint("main", key)
                return r
            except Exception:
                return default

    def _get_all_config(self):
        self.File_Ip = self.get_conf("file_ip", str)
        self.File_Port = self.get_conf("file_port", int)
        self.Data_Ip = self.get_conf("data_ip", str)
        self.Data_Port = self.get_conf("data_port", int)
        self.Protocol_Len = self.get_conf("protocol_len", int)
        self.Data_Len = self.get_conf("data_len", int)
        self.Sort_Type = self.get_conf("sort", int)
        self.Update_Interval = self.get_conf("update_interval", int)


Config_Impl = Config()
