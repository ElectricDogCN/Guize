# Listing request clock repair

The Windows request observer samples UTC before and after the HTTP operation and also records monotonic nanoseconds. Equal UTC samples were rejected by the mapper even when monotonic time showed a positive duration. The frozen provider-page validator already accepts equal aware request timestamps.

The mapper now permits equal UTC samples and continues to require a positive monotonic interval and an aware provider Date. The regression runs through bind_page and confirms equal UTC can bind the observed objects. Reversed UTC and zero or reversed monotonic time fail before mapper state is changed.

The change belongs to POC-005 under its existing source ownership and registered branch. It does not grant new execution qualification. Source gates, complete official CI and independent review remain required. Historical measurements keep their original source bindings.
