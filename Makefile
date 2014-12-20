# note: this isn't needed for building BAM
# its just for some convenience targets.

# pep8 test
PY_FILES=$(shell find $(PWD)/bam -type f -name '*.py')
pep8: FORCE
	- flake8 $(PY_FILES) --ignore=E501,E302,E123,E126,E128,E129,E124,E122 > pep8.log
	gvim --nofork -c "cfile pep8.log" -c "cope" -c "clast"

test: FORCE
	python3 ./tests/test_cli.py

doc: FORCE
	$(MAKE) -C doc html
	@echo "xdg-open doc/build/html/index.html"

clean: FORCE
	$(MAKE) -C doc clean

FORCE:
