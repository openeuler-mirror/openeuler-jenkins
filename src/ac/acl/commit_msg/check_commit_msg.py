import logging
import subprocess
import os

from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, SUCCESS

logger = logging.getLogger("ac")


class CheckCommitMsg(BaseCheck):
    """
    check commit msg
    """

    def __init__(self, workspace, repo, conf=None):
        """

        :param workspace:
        :param repo:
        :param conf:
        """
        super(CheckCommitMsg, self).__init__(workspace, repo, conf)

        # wait to initial
        self._pr_number = None
        self._tbranch = None
        self._repo = repo
        self._work_dir = workspace
    
    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check %s commit msg ...", self._repo)
        logger.debug("args: %s, kwargs: %s", args, kwargs)
        checkcommit = kwargs.get("codecheck", {})

        self._pr_number = checkcommit.get("pr_number", "")
        self._tbranch = kwargs.get("tbranch", None)
        return self.start_check()
    
    @staticmethod
    def get_commit_msg_result(commit_list, work_dir, gitlint_dir):
        commit_check_dist = {}
        try:
            for commit in commit_list:            
                commit = str(commit, encoding='utf-8')
                commit = commit.replace('\r', '')
                commit = commit.replace('\n', '')
                # get commit and add to dist for follow using
                command = "gitlint --commit " + commit + " -C " + gitlint_dir + "/.gitlint"
                res = subprocess.Popen(command, cwd=work_dir, shell=True, stderr=subprocess.PIPE)
                out = res.stderr.readlines()
                if len(out) > 0 :
                    out_str = ""
                    for line in out:
                        out_str += str(line, encoding='utf-8')
                    commit_check_dist[commit] = out_str
        except Exception as e:
            logger.warning(e)
        return commit_check_dist
    
    def check_commit_msg(self):
        """
        开始进行commitmsgcheck检查
        """
        # prepare git branch environment
        repo_dir = self._work_dir + "/" + self._repo
        logger.info("repoDir: %s", repo_dir)
        branch_log_cmd = "git fetch origin +refs/heads/{}:refs/remotes/origin/{}".format(self._tbranch, self._tbranch)
        branch_log_pro = subprocess.Popen(branch_log_cmd, cwd=repo_dir, shell=True, stdout=subprocess.PIPE)
        logger.info("git featch res: ")
        logger.info(branch_log_pro.stdout.read())
        branch_log_cmd = "git log HEAD...origin/" + self._tbranch + " --no-merges --pretty=%H"
        branch_log_pro = subprocess.Popen(branch_log_cmd, cwd=repo_dir, shell=True, stdout=subprocess.PIPE)
        branch_log_res = branch_log_pro.stdout.readlines()
        conf_dir = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../../conf/"))
        commit_check_dist = self.get_commit_msg_result(branch_log_res, repo_dir, conf_dir)
        if len(commit_check_dist) > 0:
            log_format = """
commit specifications is:
script: title

this is commit body

Signed-off-by: example example@xx.com
the folowint commits do not conform to the specifications:
        """
            logger.info(log_format)
            logger.info("==============================================================")
            for commit, check_res in commit_check_dist.items():
                logger.info("commit: %s", commit)
                logger.info("check result: \n\r %s", check_res)
                logger.info("==============================================================")
            return FAILED
        return SUCCESS
