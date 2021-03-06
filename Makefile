APPNAME = server-syncstorage
DEPS = 
VIRTUALENV = virtualenv
NOSE = bin/nosetests -s --with-xunit
TESTS = syncstorage/tests
PYTHON = bin/python
EZ = bin/easy_install
COVEROPTS = --cover-html --cover-html-dir=html --with-coverage --cover-package=keyexchange
COVERAGE = bin/coverage
PYLINT = bin/pylint
PKGS = syncstorage
EZOPTIONS = -U -i $(PYPI)
PYPI = http://pypi.python.org/simple
PYPI2RPM = bin/pypi2rpm.py --index=$(PYPI)
PYPIOPTIONS = -i $(PYPI)
BUILDAPP = bin/buildapp
BUILDRPMS = bin/buildrpms
PYPI = http://pypi.python.org/simple
CHANNEL = dev
RPM_CHANNEL = dev
PIP_CACHE = /tmp/pip-cache.${USER}
BUILD_TMP = /tmp/syncstorage-build.${USER}
INSTALL = bin/pip install
INSTALLOPTIONS = -U -i $(PYPI)

ifdef PYPIEXTRAS
	PYPIOPTIONS += -e $(PYPIEXTRAS)
	INSTALLOPTIONS += -f $(PYPIEXTRAS)
endif

ifdef PYPISTRICT
	PYPIOPTIONS += -s
	ifdef PYPIEXTRAS
		HOST = `python -c "import urlparse; print urlparse.urlparse('$(PYPI)')[1] + ',' + urlparse.urlparse('$(PYPIEXTRAS)')[1]"`

	else
		HOST = `python -c "import urlparse; print urlparse.urlparse('$(PYPI)')[1]"`
	endif

endif

INSTALL += $(INSTALLOPTIONS)

.PHONY: all build test cover build_rpms mach update

all:	build

build:
	$(VIRTUALENV) --no-site-packages --distribute .
	$(INSTALL) Distribute
	$(INSTALL) MoPyTools
	$(INSTALL) nose
	$(INSTALL) coverage
	$(INSTALL) WebTest
	$(BUILDAPP) -c $(CHANNEL) $(PYPIOPTIONS) $(DEPS)
	# umemcache doesn't work with pypi2rpm, so it can't be listed
	# in the req files.  Install by hand.
	$(INSTALL) umemcache
	# repoze.lru install seems to conflict with repoze.who, but
	# reinstalling fixes it.  Possible easy_install-vs-pip silliness.
	./bin/pip uninstall -y repoze.lru
	$(INSTALL) repoze.lru
	./bin/pip uninstall -y zope.deprecation
	$(INSTALL) zope.deprecation


update:
	$(BUILDAPP) -c $(CHANNEL) $(PYPIOPTIONS) $(DEPS)

test:
	# Check that flake8 passes before bothering to run anything.
	# This can really cut down time wasted by typos etc.
	./bin/flake8 syncstorage
	# Run the actual testcases.
	$(NOSE) $(TESTS)
	# Test that live functional tests can run correctly, by actually
	# spinning up a server and running them against it.
	./bin/paster serve syncstorage/tests/tests.ini & SERVER_PID=$$! ; sleep 2 ; ./bin/python syncstorage/tests/functional/test_storage.py http://localhost:5000 ; kill $$SERVER_PID

cover:
	$(NOSE) --with-coverage --cover-html --cover-package=syncstorage $(TESTS)

build_rpms:
	rm -rf rpms
	mkdir -p  rpms ${BUILD_TMP}
	$(BUILDRPMS) -c $(RPM_CHANNEL) $(PYPIOPTIONS) $(DEPS)
	# The pygments rpm conflicts with a system package.
	# Just remove it and depend on the system version.
	rm -f $(CURDIR)/rpms/python26-pygments*.rpm
	# umemcache doesn't play nicely with pypi2rpm.
	# Ergo, we have to build it by hand.
	wget -O ${BUILD_TMP}/umemcache.tar.gz https://github.com/esnme/ultramemcache/archive/ad77f6df02b026f0160e8a95321bb0df36647ef6.tar.gz
	cd ${BUILD_TMP}; tar -xzvf umemcache.tar.gz
	HERE=`pwd` ; cd ${BUILD_TMP}/ultramemcache-*; $$HERE/bin/python setup.py  --command-packages=pypi2rpm.command bdist_rpm2 --binary-only --name=python26-umemcache --dist-dir=$(CURDIR)/rpms
	rm -rf ${BUILD_TMP}


mock: build build_rpms
	mock init
	mock --install python26 python26-setuptools
	cd rpms; wget http://mrepo.mozilla.org/mrepo/5-x86_64/RPMS.mozilla-services/libmemcached-devel-0.50-1.x86_64.rpm
	cd rpms; wget http://mrepo.mozilla.org/mrepo/5-x86_64/RPMS.mozilla-services/libmemcached-0.50-1.x86_64.rpm
	cd rpms; wget http://mrepo.mozilla.org/mrepo/5-x86_64/RPMS.mozilla-services/gunicorn-0.11.2-1moz.x86_64.rpm
	cd rpms; wget http://mrepo.mozilla.org/mrepo/5-x86_64/RPMS.mozilla/nginx-0.7.65-4.x86_64.rpm
	mock --install rpms/*
	mock --chroot "python2.6 -m syncstorage.run"
