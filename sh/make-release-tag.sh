git_commit=$( git rev-parse --short HEAD )
date_time=$(date +'%Y%m%d%H%M')
tag=${date_time}-${git_commit}
echo ${tag}
