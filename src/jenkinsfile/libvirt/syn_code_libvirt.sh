#!/bin/bash -x
# - repo
# - minimum_prid
# - git_user_name
# - git_user_email
## - gitee_username
## - gitee_password
## - gitee_token

rpms=(python3)
sudo rm -f *.rpm
sudo yum downgrade -y "${rpms[@]}" --downloadonly --downloaddir=./ --allowerasing --skip-broken --nobest || true
sudo yum install -y "${rpms[@]}" --downloadonly --downloaddir=./ --allowerasing --skip-broken --nobest
sudo rpm -Uvh --force --nodeps *.rpm || true
sudo ln -s python3 /usr/bin/python || true

get_branches()
{
    local owner=$1
    local repo=$2
    curl -X GET --header "Content-Type: application/json;charset=UTF-8" "https://gitee.com/api/v5/repos/$owner/$repo/branches" --insecure | python -c "import sys, json; print('\n'.join(['%s' % (b['name'],) for b in json.load(sys.stdin)]))"
}

get_pulls_prid_branch()
{
    local owner=$1
    local repo=$2
    local state=$3
    curl -X GET --header "Content-Type: application/json;charset=UTF-8" "https://gitee.com/api/v5/repos/$owner/$repo/pulls?state=$state&sort=updated&direction=desc&page=1&per_page=20" --insecure | python -c "import sys, json; print('\n'.join(['%s %s %s' % (pr['merged_at'], pr['number'], pr['base']['ref']) for pr in json.load(sys.stdin)]))" | sort | awk '{print$2,$3}'
}

get_commits_hash()
{
    local owner=$1
    local repo=$2
    local prid=$3
    curl -X GET --header "Content-Type: application/json;charset=UTF-8" "https://gitee.com/api/v5/repos/$owner/$repo/pulls/$prid/commits" --insecure | python -c "import sys, json; print('\n'.join(['%s' % (c['sha'],) for c in json.load(sys.stdin)]))" | tac
}

create_pull()
{
    local owner=$1
    local repo=$2
    local branch=$3
    local tbranch=$4
    local title=$5
    local body=$6
    curl -X POST --header "Content-Type: application/json;charset=UTF-8" "https://gitee.com/api/v5/repos/$owner/$repo/pulls" -d "{\"access_token\":\"$gitee_token\",\"title\":\"$title\",\"head\":\"$gitee_username:$branch\",\"base\":\"$tbranch\",\"body\":\"$body\"}"
}

fetch_git()
{
    local repo=$1
    [ $fetch_git -eq 0 ] || return 0

    git config --global user.name "$git_user_name"
    git config --global user.email "$git_user_email"

    # rm -rf "src-$repo" "$repo"
    rm -rf "src-$repo" "$repo"
    [ -d "src-$repo" ] || git clone "https://$gitee_username:$gitee_password@gitee.com/$gitee_username/src-$repo.git" "src-$repo"
    [ -d "$repo" ] || git clone "https://gitee.com/openeuler/$repo.git" "$repo"

    cd "src-$repo"
    git remote add upstream "https://gitee.com/src-openeuler/$repo.git" || true
    git fetch upstream
    git clean -fdx

    cd "../$repo"
    sed -i "/fetch = +refs\/pull\/.*\/head/d" .git/config
    git config --add remote.origin.fetch "+refs/pull/*/head:refs/pull/*/head"
    git fetch

    fetch_git=1
}

fetch_git=0
tbranches=""
branches=$(get_branches src-openeuler "$repo")
open_pulls=$(get_pulls_prid_branch src-openeuler "$repo" open)
while read line
do
    prid=${line%% *}
    tbranch=${line#* }
	if [ "$tbranch" == "libvirt-6.2.0" ];then
    	tbranch="master"
    fi
    [ -n "$prid" ] || continue
    [ -n "$tbranch" ] || continue

    [ $prid -gt $minimum_prid ] || continue
    
    echo "$branches" | grep -q "^$tbranch$" || continue
    echo "$open_pulls" | grep " $tbranch$" && continue || true
    fetch_git "$repo"

    #From openeuler "openEuler-20.03-LTS-Next" branch to src-openeuler "openEuler-20.03-LTS-Next and openEuler-20.03-LTS-SP1" branch
    if [ "$tbranch" == "openEuler-20.03-LTS-Next" ];then
          more_tbranchs="$tbranch openEuler-20.03-LTS-SP1"
    else
          more_tbranchs=$tbranch
    fi

    for tbranch in $more_tbranchs   #only for openEuler-20.03-LTS-SP1 branch
    do
      cd "../src-$repo"
      git checkout -f "$tbranch" || git checkout -b "$tbranch"
      echo "$tbranches " | grep " $tbranch " || git reset --hard "upstream/$tbranch"
      git log | grep -w "spec: Update patch and changelog with !$prid" && continue || true
      echo "$tbranches " | grep " $tbranch " || tbranches="$tbranches $tbranch"
  
      cd "../$repo"
      git checkout -f "pull/$prid/head"
      git reset --hard "pull/$prid/head"
  
      cd "../src-$repo"
      from_hash=$(git show -s --format=%H)
      changelog=$(awk '/^%changelog/{print NR}' "$repo.spec" | tail -n 1)
      patch_line=$(awk '/^[Pp][Aa][Tt][Cc][Hh][0-9]+: /{print NR}' "$repo.spec" | tail -n 1)
      patch_id=$(awk -F: -v line=$patch_line 'NR==line{print$1}' "$repo.spec" | sed "s/^[^0]*0*//")
      while read hash
      do
          patch_file=$(cd "../$repo" && git format-patch -1 "$hash")
          mv "../$repo/$patch_file" "${patch_file#0001-}"
          patch_file=${patch_file#0001-}
          git add "$patch_file"
  
          author_name="Huawei Technologies Co., Ltd"
          author_email="alex.chen@huawei.com"
          author_date=$(cd "../$repo" && git show -s --format=%ad "$hash")
          subject=$(cd "../$repo" && git show -s --format=%s "$hash")
          message=$(cd "../$repo" && git show -s --format=%s%n%n%b "$hash")
          git commit --author="$author_name <$author_email>" --date="$author_date" --message="$message"
          ((patch_id++))
          sed -i "$patch_line a Patch$(printf "%04d" $patch_id): ${patch_file#0001-}" "$repo.spec"
          ((patch_line++))
  
          [ $patch_line -le $changelog ] && ((changelog++)) || true
          sed -i "$changelog a - $subject" "$repo.spec"
          ((changelog++))
      done <<< "$(get_commits_hash openeuler "$repo" "$prid")"
    
      now_date=$(date "+%a %b %d %H:%M:%S %Y %z")
  
      sed -i "$changelog G" "$repo.spec"
      sed -i "/^%changelog/a * $(echo "$now_date" | awk '{print$1,$2,$3,$5}') $author_name <$author_email>" "$repo.spec"
      #sed -i "/^%changelog/a * $(echo "$author_date" | awk '{print$1,$2,$3,$5}') $author_name <$author_email>" "$repo.spec"
      # sed -i "/^%changelog/a * $(echo "$author_date" | awk '{print$1,$2,$3,$5}') Huawei Technologies Co., Ltd <$author_email>" "$repo.spec"
      spec_subject="spec: Update patch and changelog with !$prid"
      spec_body=$(git show -s --format=%s "$from_hash..HEAD" | tac)
      spec_signoff=$(git show -s --format=%b "$from_hash..HEAD" | awk '$1=="Signed-off-by:"' | sort -u)
      spec_message="$spec_subject"$'\n\n'"$spec_body"$'\n\n'"$spec_signoff"
      git commit --message="$spec_message" "$repo.spec"
    done
done <<< "$(get_pulls_prid_branch openeuler "$repo" merged)"

for tbranch in $tbranches
do
    cd "../src-$repo"
    echo $tbranch
    git checkout "$tbranch"
    release=$(awk '/^Release: /{print$2}' "$repo.spec")
    sed -i "s/^Release: .*/Release: $((release+1))/" "$repo.spec"
    prids=$(git show -s --format=%s "upstream/$tbranch..HEAD" | awk '/spec: Update patch and changelog with ![0-9]+/{print$NF}' | tac | xargs)
    spec_message="spec: Update release version with $prids"$'\n\n'"increase release version by one"
    git commit --signoff --message="$spec_message" "$repo.spec"

    git push --force origin "$tbranch"
    pull_body=$(git show -s --format=%s "upstream/$tbranch..HEAD" | sed "/spec: Update patch and changelog with ![0-9]\+/{x;p;x;}")
    create_pull src-openeuler "$repo" "$tbranch" "$tbranch" "Automatically generate code patches with openeuler $prids" "<pre>$pull_body</pre>"
done
