#!/usr/bin/perl -w
 

use File::Spec::Functions qw(rel2abs);
use File::Basename qw(dirname);
use Getopt::Std;
use POSIX;
use Data::Dumper;
use XML::Structured;
use strict;

our $services = [
    'services' =>
     [[ 'service' =>
            'name',
            'mode', # "localonly" is skipping this service on server side, "trylocal" is trying to merge changes directly in local files, "disabled" is just skipping it
         [[ 'param' =>
	        'name',
                '_content'
         ]],
    ]],
];

die " USAGE: $0 -f service_file -p product -c code_dir -m module -w workdir\n" if (@ARGV < 5);

our ($opt_f,$opt_p,$opt_c,$opt_m,$opt_w) =("","","","","");

&getopts("Hf:p:c:m:w:");

my $service_file = $opt_f if ($opt_f);
my $product = $opt_p if ($opt_p);
my $code_dir = $opt_c if ($opt_c);
my $module = $opt_m if ($opt_m);
my $myworkdir = $opt_w if ($opt_w);

#open lg, ">/home/test.log";

my $xml_file = readstr($service_file);
my $serviceinfo = XMLin($services, $xml_file);
for my $service (@{$serviceinfo->{'service'}}) {
  #print lg "Run for ".getcwd. "/$service->{'name'}"."\n";
  my @run;

  push @run, dirname(rel2abs($0))."/$service->{'name'}";
  for my $param (@{$service->{'param'}}) { 
    if ($service->{'name'} eq 'recompress') {
    	push @run, "--$param->{'name'}";
    	if ($param->{'name'} eq 'file') {
        	push @run, $myworkdir.'/'.$param->{'_content'};
#		print lg '--'. $param->{'name'} . " ".$myworkdir.'/'.$param->{'_content'}."\n";
 	}
   	else {
       	 	push @run, $param->{'_content'};
#		print lg '--'. $param->{'name'}. " " .$param->{'_content'}."\n";
    	}
#		print lg '--outdir '. $myworkdir."\n";
    } else {
        if ($param->{'name'} eq 'submodules'){
            print 'skip submodules para';
        }else{
	        next if $param->{'name'} eq 'outdir';
	        next unless $param->{'_content'};
	        push @run, "--$param->{'name'}";
		    push @run, $param->{'_content'};
        }
	}
  }
  
  push @run, "--outdir";
  push @run, "$myworkdir";
  
  if ($service->{'name'} =~ /tar/) {
      push @run, "--project";
      push @run, "$product";

      push @run, "--package";
      push @run, "$module";
  }
 
  print @run;
  system(@run);
}

sub readstr {
  my ($fn, $nonfatal) = @_;
  local *F;
  if (!open(F, '<', $fn)) {
    die("$fn: $!\n") unless $nonfatal;
    return undef;
  }
  my $d = '';
  1 while sysread(F, $d, 8192, length($d));
  close F;
  return $d;
}
