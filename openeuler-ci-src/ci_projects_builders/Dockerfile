FROM openeuler/openeuler:21.03

RUN yum update && \
    yum install -y vim wget git xz tar make automake autoconf libtool gcc gcc-c++ kernel-devel libmaxminddb-devel pcre-devel openssl openssl-devel tzdata \
        readline-devel libffi-devel python3-devel mariadb-devel python3-pip net-tools.x86_64 iputils

RUN pip3 install uwsgi

WORKDIR /work/ci_projects_builders

COPY . /work/ci_projects_builders

RUN pip3 install -r requirements.txt

ENV LANG=en.US_UTF-8

ENTRYPOINT ["uwsgi", "--ini", "/work/ci_projects_builders/deploy/production/uwsgi.ini"]
