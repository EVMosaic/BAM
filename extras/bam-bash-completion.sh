# bam-bash-completion.sh.sh parameter-completion

_bam_complete_find_root()
{
	PARENT=""
	GRANDPARENT="../"
	unset BAM_ROOT

	while [ ! -d "$GRANDPARENT/.bam" ] && [ "$GRANDPARENT" != "/" ] ; do
		PARENT=$GRANDPARENT
		GRANDPARENT="$(realpath $PARENT/..)"
	done

	if [ ! -z "$GRANDPARENT" ] && [ "$GRANDPARENT" != "/" ] ; then
		BAM_ROOT=$GRANDPARENT
	fi
	unset PARENT GRANDPARENT
}

_bam_complete()
{
	local cur
	local cur_path
	local cur_cmd

	COMPREPLY=()   # Array variable storing the possible completions.
	cur=${COMP_WORDS[COMP_CWORD]}
	cur_cmd=""

	# {a,b,c} -> a b c
	subcommands=$(bam --help | grep -e "valid subcommands" -A2 | \
	              tail -n-1 | tr -d '[[:space:]]' | sed "s/\,/ /g" | sed s/\{//g | sed s/\}//g)

	for i in $(seq 1 $COMP_CWORD); do
		if [[ ${COMP_WORDS[i]} =~ ^($subcommands_re)$ ]]; then
			cur_cmd="${COMP_WORDS[i]}"
			break
		fi
	done

	if [[ -z "$cur_cmd" ]] ; then
		# a b c -> a|b|c
		subcommands_re=$(sed "s/ /\|/g"<<<$subcommands)

		# print all subcommands since we didn't enter in any
		COMPREPLY=($(compgen -W "$subcommands" -- $cur))
	else
		case "$cur" in
			-*)
				COMPREPLY=($(compgen -W "$(bam $cur_cmd --help | grep "optional arguments" -A1000 | \
				           tail -n+2 | sed s/\,//g | sed s/\\s/\\n/g | grep -e '^\-')" -- $cur));;
			*)
				_bam_complete_find_root
				if [[ ! -z "$BAM_ROOT" ]] ; then
					cur_path=`dirname $cur"_"`"/"
					COMPREPLY=($(compgen -W "$(bam list $cur_path --full)" -- $cur))
				fi
			;;
		esac
	fi

	return 0
}

complete -F _bam_complete -o filenames bam

