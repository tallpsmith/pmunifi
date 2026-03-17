Name:           pcp-pmda-unifi
Version:        @@VERSION@@
Release:        1%{?dist}
Summary:        PCP PMDA for UniFi network monitoring
License:        GPL-2.0-or-later
URL:            https://github.com/tallpsmith/pmunifi
Source0:        %{wheel_file}
Source1:        pmdaunifi.1

BuildArch:      noarch

Requires:       pcp
Requires:       python3-pcp
Requires:       python3-requests

%description
Performance Co-Pilot (PCP) Performance Metrics Domain Agent (PMDA) for
Ubiquiti UniFi network infrastructure. Polls UniFi controllers via REST
API and exposes switch port traffic, device inventory, site health,
gateway WAN/LAN metrics, client tracking, AP radio, and DPI metrics
through the standard PCP toolchain.

%prep
# Nothing to unpack — we install from the pre-built wheel

%build
# Wheel is pre-built

%install
pip3 install --root=%{buildroot} --prefix=/usr --no-deps --no-compile \
    %{SOURCE0}

# Discover where pip installed the package
SITELIB=$(find %{buildroot} -type d -name pcp_pmda_unifi -path "*/site-packages/*" | head -1)
SITELIB_REL=${SITELIB#%{buildroot}}
SITELIB_DIR=$(dirname "$SITELIB_REL")

# Install man page
install -d %{buildroot}%{_mandir}/man1
install -m 0644 %{SOURCE1} %{buildroot}%{_mandir}/man1/pmdaunifi.1

# Create PMDA directory structure
install -d %{buildroot}/var/lib/pcp/pmdas/unifi

# Deploy PMDA assets from the installed package
install -m 0755 "$SITELIB/deploy/Install" %{buildroot}/var/lib/pcp/pmdas/unifi/
install -m 0755 "$SITELIB/deploy/Remove"  %{buildroot}/var/lib/pcp/pmdas/unifi/
install -m 0644 "$SITELIB/deploy/unifi.conf.sample" %{buildroot}/var/lib/pcp/pmdas/unifi/

# Save sitelib path for %files
echo "$SITELIB_DIR" > %{buildroot}/.sitelib_dir

%post
# Register the PMDA with PMCD
cd /var/lib/pcp/pmdas/unifi && ./Install -u </dev/null >/dev/null 2>&1
exit 0

%preun
if [ "$1" = "0" ]; then
    # Package removal (not upgrade) — deregister from PMCD
    cd /var/lib/pcp/pmdas/unifi && ./Remove </dev/null >/dev/null 2>&1
fi
exit 0

%files
/usr/lib/python*/site-packages/pcp_pmda_unifi/
/usr/lib/python*/site-packages/pcp_pmda_unifi-*.dist-info/
%dir /var/lib/pcp/pmdas/unifi
/var/lib/pcp/pmdas/unifi/Install
/var/lib/pcp/pmdas/unifi/Remove
/var/lib/pcp/pmdas/unifi/unifi.conf.sample
%{_bindir}/unifi2dot
%{_bindir}/pcp-pmda-unifi-setup
%{_mandir}/man1/pmdaunifi.1*
%exclude /.sitelib_dir

%changelog
* Sun Mar 16 2026 pmdaunifi contributors - @@VERSION@@-1
- Initial package
