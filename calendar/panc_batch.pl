#!/usr/bin/perl
# Batch front end to pancanga313_ns_test.pl (Yano & Fushimi, Pancanga 3.13; path in $PANCANGA), for Kathmandu.
# Dates are the program's "modern" dates: Julian calendar before 15 Oct 1582, Gregorian after.
# One query per line, one answer per line:
#   T id saka_year masa_num paksa(s|k) tithi  -> id year month day weekday julian_day
#        the civil day of that (amanta) tithi; masa_num 0 = Caitra ... 11 = Phalguna
#   J id julian_day                           -> id year month day weekday saka masa paksa tithi naksatra julian_day
#        the pancanga of that civil day (at sunrise); masa is prefixed with 'Adhika-' in an intercalary month
$| = 1;
$pancanga_as_sub = 1;
require "$ENV{PANCANGA}";
$loc_lat = 27.7; $loc_lon = 85.3; $desantara = ($loc_lon - $Ujjaini_lon) / 360;

sub squeeze { my $s = shift; $s =~ s/\s+//g; $s }

while (<STDIN>) {
    chomp; next unless /\S/;
    my @f = split /\s+/;
    if ($f[0] eq 'J') {
        my $jd = $f[2];
        ($year, $month, $day) = &JulianDay_to_ModernDate($jd);
        &cache_variable_clear;
        &calculations;
        my $ad = &squeeze($adhimasa);
        printf "%s %d %d %d %s %d %s%s %s %d %s %.1f\n", $f[1], $year, $month, &trunc($day), $weekday_name,
            $YearSaka, ($ad ne '' ? 'Adhika-' : ''), &squeeze($masa), $sukla_krsna, $tithi_day, &squeeze($naksatra), $jd;
    } elsif ($f[0] eq 'T') {
        my ($id, $saka, $m, $p, $t) = @f[1..5];
        $YearSaka = $saka; $masa_num = $m; $tithi_day = $t;
        $paksa = ($p eq 'k') ? 'Krsnapaksa' : 'Suklapaksa';
        &cache_variable_clear;
        &try_calculations;
        printf "%s %d %d %d %s %.1f\n", $id, $year, $month, &trunc($day), $weekday_name, $JulianDay;
    } else {
        print "$f[1] ERROR unknown query\n";
    }
}
