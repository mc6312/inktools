packer = tar
pack = $(packer) caf
unpack = $(packer) --keep-newer-files xaf
arcx = .tar.xz
todo = TODO
docs = Changelog LICENSE README.md $(todo)
basename = inktools
srcversion = inkavail
version = $(shell python3 -c 'from $(srcversion) import VERSION; print(VERSION)')
branch = $(shell git symbolic-ref --short HEAD)
title_version = $(shell python3 -c 'from $(srcversion) import TITLE_VERSION; print(TITLE_VERSION)')
zipname = $(basename).zip
arcname = $(basename)$(arcx)
srcarcname = $(basename)-$(branch)-src$(arcx)
srcs = *.py
resources = *.svg *.ui
backupdir = ~/shareddocs/pgm/python/

app:
	zip -9 $(zipname) $(srcs) $(resources)
	@echo '#!/usr/bin/env python3' >$(basename)
	@cat $(zipname) >>$(basename)
	rm $(zipname)
	chmod 755 $(basename)

archive:
	make todo
	$(pack) $(srcarcname) *.py *.ui *.svg *.org Makefile *.geany $(docs)
distrib:
	make app
	$(eval distname = $(basename)-$(version)$(arcx))
	$(pack) $(distname) $(basename) $(docs)
	mv $(distname) ~/downloads/
backup:
	make archive
	mv $(srcarcname) $(backupdir)
update:
	$(unpack) $(backupdir)$(srcarcname)
commit:
	make todo
	git commit -a -uno -m "$(version)"
docview:
	$(eval docname = README.htm)
	@echo "<html><head><meta charset="utf-8"><title>$(title_version) README</title></head><body>" >$(docname)
	markdown_py README.md >>$(docname)
	@echo "</body></html>" >>$(docname)
	x-www-browser $(docname)
	#rm $(docname)
show-branch:
	@echo "$(branch)"
todo:
	pytodo.py $(srcs) >$(todo)
edit-db:
	emacs --no-desktop -nw inks.org
