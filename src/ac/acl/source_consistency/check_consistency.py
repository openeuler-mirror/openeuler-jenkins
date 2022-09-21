import hashlib
import logging
import os
import re
import stat
import shutil
import sqlite3
from sqlite3 import Error

from src.ac.common.gitee_repo import GiteeRepo
from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, SUCCESS, WARNING

logger = logging.getLogger("ac")


class CheckSourceConsistency(BaseCheck):
    """
    check source consistence
    """

    def __init__(self, workspace, repo, conf=None):
        super(CheckSourceConsistency, self).__init__(workspace, repo, conf)

        self._work_dir = os.path.join(workspace, "source_consistency")
        shutil.copytree(os.path.join(workspace, repo), self._work_dir)
        self._repo = repo
        self.temp_txt_path = os.path.join(self._work_dir, "temp.txt")
        self.rpmbuild_dir = os.path.join(workspace, "rpmbuild")
        self.rpmbuild_build_path = os.path.join(self.rpmbuild_dir, "BUILD")
        self.rpmbuild_sources_path = os.path.join(self.rpmbuild_dir, "SOURCES")
        self.database_path = "source_clean.db"
        self.con = self.create_connection()

    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check %s source consistency ...", self._repo)
        _ = not os.path.exists("log") and os.mkdir("log")
        try:
            return self.start_check_with_order("source_consistency")
        finally:
            if self.con is not None:
                self.con.close()
            self.clear_temp()

    @staticmethod
    def get_package_from_source(url):
        """
        从url中获取包名
        """
        package_name = url.split("/")[-1].strip()
        return package_name

    @staticmethod
    def get_sha256sum(package):
        """
        计算文件的sha256sum值
        """
        logger.info("getting sha256sum of native source package...")
        native_sha256sum = ""
        try:
            with open(package, "rb") as f:
                sha256obj = hashlib.sha256()
                sha256obj.update(f.read())
                native_sha256sum = sha256obj.hexdigest()
        except Exception as e:
            logger.warning(e)
        if native_sha256sum == "":
            try:
                native_sha256sum = os.popen("sha256sum {0}".format(package)).read().split()[0]
            except Exception as e:
                logger.warning(e)
        return native_sha256sum.strip()

    def check_source_consistency(self):
        """
        检查源码包是否一致
        """
        os.makedirs(os.path.join(self.rpmbuild_dir, "SOURCES"), exist_ok=True)
        source_url = self.get_source_url()
        if source_url == "":
            logger.warning("no valid source url")
            return WARNING

        package_name = self.get_package_from_source(source_url)
        if package_name not in os.listdir(self._work_dir):
            logger.warning("no source package file")
            return WARNING

        native_sha256sum = self.get_sha256sum(os.path.join(self._work_dir, package_name))
        if native_sha256sum == "":
            logger.warning("get sha256sum of native source package failed")
            return WARNING

        remote_sha256sum = self.get_sha256sum_from_url(source_url)
        if remote_sha256sum == "":
            logger.warning("no url in source_clean.db")
            return WARNING
        if native_sha256sum != remote_sha256sum:
            logger.error("repo is inconsistency")
            return FAILED

        return SUCCESS

    def get_source_url(self):
        """
        获取spec文件中的Source URL
        """
        spec_name = ""
        files_list = os.listdir(self._work_dir)
        if len(files_list) == 0:
            logger.error("copy repo error, please check!")
            return ""
        if self._repo + ".spec" not in files_list:
            logger.warning("no such spec file: " + self._repo + ".spec")
            for file_name in files_list:
                if file_name.endswith(".spec"):
                    spec_name = file_name
                    break
            if spec_name == "":
                logger.error("no spec file, please check!")
                return ""
        source_url = self.get_source_from_rpmbuild(spec_name)
        return source_url

    def get_source_from_rpmbuild(self, spec_name=""):
        """
        rpmbuild解析出可查询的Source URL
        """
        if spec_name == "":
            spec_name = self._repo + "spec"
        spec_file = os.path.join(self._work_dir, spec_name)
        self.generate_new_spec(spec_file)
        source_url = self.do_rpmbuild()
        return source_url

    def generate_new_spec(self, spec_file):
        """
        读取spec文件并生成新的spec文件
        """
        logger.info("reading spec file : %s ...", os.path.basename(spec_file))

        new_spec_file = os.path.join(self.rpmbuild_sources_path, "get_source.spec")
        cond_source = re.compile("^Source0*")
        source_url = ""
        new_spec_content = ""
        with open(spec_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("%prep"):
                    break
                elif cond_source.match(line) or re.match("^Source.*", line):
                    if source_url == "":
                        if ":" in line:
                            source_url = ":".join(line.split(":")[1:]).strip()
                new_spec_content += line + os.linesep
        new_spec_content += self.get_prep_function(source_url)
        logger.info("generating new spec file ...")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        modes = stat.S_IWUSR | stat.S_IRUSR
        with os.fdopen(os.open(new_spec_file, flags, modes), 'w') as f:
            f.write(new_spec_content)

    def get_prep_function(self, url):
        """
        生成spec文件%prep部分的内容
        """
        logger.info("generating %prep function")
        function_content = "%prep" + os.linesep
        function_content += "source={0}".format(url) + os.linesep
        function_content += "cd {0}".format(self.rpmbuild_sources_path) + os.linesep
        function_content += "echo $source > {0}".format(self.temp_txt_path) + os.linesep
        return function_content

    def do_rpmbuild(self):
        """
        对新生成的spec文件执行rpmbuild
        """
        logger.info("start to do rpmbuild")
        new_spec_file = os.path.join(self.rpmbuild_sources_path, "get_source.spec")
        res = os.system("rpmbuild -bp --nodeps {0} --define \"_topdir {1}\"".format(new_spec_file, self.rpmbuild_dir))
        if res != 0:
            logger.error("do rpmbuild fail")
        if not os.path.exists(self.temp_txt_path):
            return ""
        with open(self.temp_txt_path, "r") as f:
            source_url = f.read().strip()
        return source_url

    def create_connection(self):
        """
        与数据库建立连接
        """
        logger.info("getting connection with source_clean.db ...")
        try:
            if os.path.exists(self.database_path):
                con = sqlite3.connect(self.database_path)
                return con
        except Error:
            logger.error(Error)
        return None

    def get_sha256sum_from_url(self, url):
        """
        查询数据库，获取url的sha256sum值
        """
        logger.info("getting sha256sum of remote source package from source_clean.db ...")
        if self.con is None:
            logger.warning("failed to connect to database")
            return ""
        cursor_obj = self.con.cursor()
        cursor_obj.execute("SELECT sha256sum FROM source_package WHERE url = ?", (url,))
        row = cursor_obj.fetchone()
        if row:
            return row[0]
        return ""

    def clear_temp(self):
        """
        清理生成的中间文件
        """
        if os.path.exists(self._work_dir):
            shutil.rmtree(self._work_dir)
        shutil.rmtree(self.rpmbuild_dir)
