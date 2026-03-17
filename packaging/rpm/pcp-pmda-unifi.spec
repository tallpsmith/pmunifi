Name:           pcp-pmda-unifi
Version:        @@VERSION@@
Release:        1%{?dist}
Summary:        PCP PMDA for UniFi network monitoring
License:        GPL-2.0-or-later
URL:            https://github.com/tallpsmith/pmunifi
Source0:        pcp_pmda_unifi-py3-none-any.whl
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

# Install man page
install -d %{buildroot}%{_mandir}/man1
install -m 0644 %{SOURCE1} %{buildroot}%{_mandir}/man1/pmdaunifi.1

# Create PMDA directory structure
install -d %{buildroot}%{_localstatedir}/lib/pcp/pmdas/unifi

# Deploy PMDA assets from the installed package
cp -a %{buildroot}%{python3_sitelib}/pcp_pmda_unifi/deploy/Install \
      %{buildroot}%{_localstatedir}/lib/pcp/pmdas/unifi/
cp -a %{buildroot}%{python3_sitelib}/pcp_pmda_unifi/deploy/Remove \
      %{buildroot}%{_localstatedir}/lib/pcp/pmdas/unifi/
cp -a %{buildroot}%{python3_sitelib}/pcp_pmda_unifi/deploy/unifi.conf.sample \
      %{buildroot}%{_localstatedir}/lib/pcp/pmdas/unifi/

# Make Install and Remove executable
chmod 0755 %{buildroot}%{_localstatedir}/lib/pcp/pmdas/unifi/Install
chmod 0755 %{buildroot}%{_localstatedir}/lib/pcp/pmdas/unifi/Remove

%post
# Register the PMDA with PMCD
cd %{_localstatedir}/lib/pcp/pmdas/unifi && ./Install -u </dev/null >/dev/null 2>&1
exit 0

%preun
if [ "$1" = "0" ]; then
    # Package removal (not upgrade) — deregister from PMCD
    cd %{_localstatedir}/lib/pcp/pmdas/unifi && ./Remove </dev/null >/dev/null 2>&1
fi
exit 0

%files
%license LICENSE
%doc README.md
%{python3_sitelib}/pcp_pmda_unifi/
%{python3_sitelib}/pcp_pmda_unifi-*.dist-info/
%dir %{_localstatedir}/lib/pcp/pmdas/unifi
%{_localstatedir}/lib/pcp/pmdas/unifi/Install
%{_localstatedir}/lib/pcp/pmdas/unifi/Remove
%{_localstatedir}/lib/pcp/pmdas/unifi/unifi.conf.sample
%{_bindir}/unifi2dot
%{_bindir}/pcp-pmda-unifi-setup
%{_mandir}/man1/pmdaunifi.1*

%changelog
* Sun Mar 16 2026 pmdaunifi contributors - @@VERSION@@-1
- Initial package
