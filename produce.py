/*                                produce
 *
 *  This Is a C Program For Converting binary data from the BSR AltAcc
 *  to ASCII Data with nice little Headers.
 *
 *   Rev  Who  Date        Description
 * =====  ===  ==========  ========================================
 * 1.25c  kjh  09-28-1998  Eliminated stderr output for DOS version
 *
 */

#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>
#include <string.h>
#include <signal.h>
#include <malloc.h>
#include <time.h>
#include <errno.h>
#include <math.h>

#define VERSION                  "1.25c"

#undef DOS                       /* gcc compiler */
// #define DOS                      /* DOS compiler */

#ifdef DOS
   #include <conio.h>
   #include <process.h>
   #include <dos.h>
   #include <bios.h>

   #define R_OK   04
   #define access _access

#else
   #include <unistd.h>
#endif

#define     TRUE           1
#define     FALSE          0

   typedef  unsigned char        byte ;
   typedef  unsigned short       u16 ;
   typedef  unsigned long        u32 ;

   typedef  struct   AP
   {
      byte  A ;
      byte  P ;
   }  AP ;

#define NUM_PAIRS 4080

/* this is the structure of the AltAcc Header ( 32 bytes ) */

   typedef  struct   AltAccDump
   {
      byte  Version   ;                /* Starting at v2-125, we have V! */
      byte  kjh_toy [3] ;              /* play data for 'special models' */
      byte  DrogueSec ;                /* Time of Drogue Deploy, Seconds */
      byte  Drogue16s ;                /* Time of Drogue Deploy, 1/16sec */
      byte  DrogueAcc ;                /* Accel at Drogue Deploy         */
      byte  DroguePre ;                /* Pressure at Drogue Deploy      */
      byte  MainSec ;                  /* Time of Main Deploy, Seconds   */
      byte  Main16s ;                  /* Time of Main Deploy, 1/16sec   */
      byte  MainAcc ;                  /* Accel at Main Deploy           */
      byte  MainPre ;                  /* Pressure at Main Deploy        */
      byte  BSFlags ;                  /* AltAcc Launch Status Flags     */
      byte  BasePre ;                  /* Pressure Reading, Win [Ptr]    */
      byte  LastPre ;                  /* Pressure Reading, Win [Ptr+3]  */
      byte  WinPtr  ;                  /* Pointer to Beginning of Win [] */
      byte  Window [4] ;               /* 4-byte circular buffer, Accel  */
      byte  AvgAcc ;                   /* Average of Window [] Data      */
      byte  NitAcc [4];                /* T={1,2,3,4} / 16 (Liftoff Acc) */
      byte  SumLob ;                   /* Lo Byte of Sum of NitAcc []    */
      byte  SumHib ;                   /* Hi Byte of Sum of NitAcc []    */
      byte  foo2 [5] ;                 /* Reserved                       */
      AP    Data [ NUM_PAIRS ] ;       /* This is the 8160 Byte Flight   */
      byte  CkSumLob ;                 /* AltAcc's Version of check sum  */
      byte  CkSumHib ;                 /* Hi Byte of same                */
      byte  O ;                        /* AltAcc sez 'O'                 */
      byte  K ;                        /* AltAcc sez 'K'                 */

   } AltAccDump ;

#define ALTACC_FILE_SIZE  sizeof ( AltAccDump )

   union DataBuf
   {
      struct   AltAccDump  Name ;
      byte                 Byte [ ALTACC_FILE_SIZE ] ;
   }  AltAccFile ;

   const char* Header [] =
   {
      "      Time  Accel  Press    Sum  Accelerat   Velocity   Altitude  PressAlt",
      "       sec  units  units  units   ft/sec^2     ft/sec       feet      feet",
      " =========  =====  =====  =====  =========  =========  =========  ========",
   } ;

   const char* ExHead [] =
   {
      "\"Time\",\"Accel\",\"Press\",\"Vel\",\"Accel\",\"Velocity\",\"IAlt\",\"PAlt\"",
      "\"sec\",\"GHarrys\",\"Orvilles\",\"Verns\",\"ft/sec^2\",\"ft/sec\",\"feet\",\"feet\"",
   } ;


#define NUM_HEADER  ( sizeof ( Header ) / sizeof ( const char* ))
#define NUM_EXHEAD  ( sizeof ( ExHead ) / sizeof ( const char* ))

   const char* Units [] =
   {
      "sec",      /*  0 */
      "in",       /*  1 */
      "ft" ,      /*  2 */
      "cm",       /*  3 */
      "m",        /*  4 */
      "km",       /*  5 */
      "oz",       /*  6 */
      "lb",       /*  7 */
      "gm",       /*  8 */
      "kg",       /*  9 */
      "inhg",     /* 10 */
      "mmhg",     /* 11 */
      "torr",     /* 12 */
      "kpa",      /* 13 */
   };

   /* default units */

   u16 U [ ] =
   {
      2,          /* ft   */
      7,          /* lb   */
      0,          /* sec  */
     10,          /* inhg */
   } ;

   extern   char   * optarg ;             /* required for lib fun getarg */
   extern   int      optind ;             /* ditto                       */

   char   * progname       ;              /* who am i, anyway ?          */
   char   * proghome       ;              /* and where am i ?            */

   int      Verbose = TRUE ;

#define     NAME_LEN_MAX       256

   FILE   * OutFileAddr ;
   char     OutFileName [ NAME_LEN_MAX+1 ] ;

   char     InpFileName [ NAME_LEN_MAX+1 ] ;

   char     CalFileName [ NAME_LEN_MAX+1 ] ;

   char     NitFileName [ NAME_LEN_MAX+1 ] ;

   char     ComFileName [ NAME_LEN_MAX+1 ] ;

   int      ComOride = FALSE ;

#define  NIT_NAME    "prodata.nit"
#define  CAL_NAME    "prodata.cal"
#define  OUT_NAME    "prodata.dat"

   int      CalOride   = FALSE;              /* When the -c is invoked (v2) */

#define   PALT_IDEAL_5100        210            /* what _my_ test unit sez  */

#define   MPX5100                0
#define   MPX4100                1

   int   XDucerType = MPX4100    ;              /* MPX Type (v1.25)         */

   const char* XDucerTypeStr [] =                     /* v125b */
          {
            "Motorola MPX5100",
            "Motorola MPX4100",
          } ;

#define   PALT_GAIN_4100         0.1113501786   /* this is the 4100 xducer */
#define   PALT_OFFSET_4100       3.418657       /* these are average lines */

#define   PALT_GAIN_5100         0.1354567027   /* this is the 5100 xducer */
#define   PALT_OFFSET_5100       1.475092       /* this is 40 mV / KPa     */

// fine   PALT_GAIN_4100         0.1760937134   /* this is the 4100 xducer */
// fine   PALT_OFFSET_4100     -12.341491       /* this is 52 mV / KPA !!! */

// fine   PALT_GAIN_5100         0.1447552322   /* this is the 5100 xducer */
// fine   PALT_OFFSET_5100      -0.478599       /* this is from test1      */

   typedef  struct   CalData
   {
      char * Tag ;
      char * Nam ;
      double Val ;
   }  CalData ;

   CalData CaliData [ ] =
   {
      { "actalt", "Actual Altitude",                0.0 },
      { "actbp",  "Actual Barometric Pressure",     0.0 },
      { "avgbp",  "AltAcc Pressure Avg",            0.0 },
      { "stdbp",  "AltAcc Pressure Std Dev",        0.0 },
      { "offbp",  "Barometric Pressure Offset",     0.0 },
      { "gainbp", "Barometric Pressure Gain Factor",1.0 },
      { "avg-1g", "Minus One Gee Avg",              0.0 },
      { "std-1g", "Minus One Gee Std Dev",          0.0 },
      { "fid(0)", "Finite Difference on [ -1, 0 ]", 0.0 },
      { "avg0g",  "Zero Gee Avg",                   0.0 },
      { "std0g",  "Zero Gee Std Dev",               0.0 },
      { "fid(1)", "Finite Difference on [ 0, 1 ]",  0.0 },
      { "avg+1g", "Plus One Gee Avg",               0.0 },
      { "std+1g", "Plus One Gee Std Dev",           0.0 },
      { "do/dg",  "Slope of AltAcc Output per G",   0.0 },
      { "y[0]",   "Y-Intercept of AltAcc Output",   0.0 },
      { "ccoff",  "Correlation Coefficient",        0.0 },
      { "xducer", "Motorola Pressure XDucer Type",  0.0 },
   } ;

#define NUM_CAL_ROWS ( sizeof ( CaliData ) /  ( sizeof ( CalData )))

#define      ActAlt     0
#define      ActBP      1
#define      AvgBP      2
#define      StDBP      3
#define      OffBP      4
#define      GainBP     5
#define      AvgNegG    6
#define      StDNegG    7
#define      FiDNegG    8
#define      AvgZeroG   9
#define      StDZeroG  10
#define      FiDZeroG  11
#define      AvgOneG   12
#define      StDOneG   13
#define      Slope     14
#define      YZero     15
#define      CCoff     16
#define      XDucer    17

   typedef  struct   NitData
   {
      char * Tag ;
      int    Ptr ;
   }  NitData ;

   NitData NitTags [ ] =
   {
      { "none",   0 },
      { "port",   1 },
      { "time",   2 },
      { "alt",    3 },
      { "vel",    4 },
      { "acc",    5 },
      { "press",  6 },
      { "cal",    7 },
      { "xducer", 8 },
   } ;

#define  NUM_NIT_TAGS   ( sizeof ( NitTags ) / sizeof ( NitData ))

#define  NT_PORT     1
#define  NT_TIME     2
#define  NT_ALT      3
#define  NT_VEL      4
#define  NT_ACC      5
#define  NT_PRESS    6
#define  NT_CAL      7
#define  NT_XDUCER   8

#ifdef DOS
   #define   DIR_SEP                '\\'     /* change for unix / mac / dos */
#else
   #define   DIR_SEP                '/'      /* change for unix / mac / dos */
#endif

#define INP_SIZE                 256
#define MAXARG                   3

#define   TICK_CHAR              0xFE
#define   COMMENT_CHAR           '#'
#define   ALTACC_DUMP_LEN        8196
#define   KEY_INP_MAX            256

#define   DEFAULT_GAIN            2.5500        /* +/- 50 G over 255 units  */
#define   GEE                    32.17          /* you know, Newton and all */
#define   dT                      0.0625        /* AltAcc dt                */
#define   TWO_dT                  0.1250        /* 2 * dT for 2-step derivs */
#define   TWELVE_dT               0.7500        /* 12 * dT for Taylors 2step*/
#define   dT_3                    0.02083333333333 /* dT / 3 for Simpson    */

#define  TIME_END                5.000          /* end report @ down+5 (v2) */
#define  TIME_MAX              255.125          /* end report @ down+5 (v2) */

#define  PRT_REG                 0
#define  PRT_CSV                 1

#define  LAUNCH_THOLD            16.0           /* about 1/4 sec of 1.33 G  */
   void           Breaker ( int );              /* Fun () Prototypes        */
   void           SafeOut ( char * );
   int            SafeIn ( void );
   void           CleanUp ( void ) ;
   void           Usage ( void ) ;
   char           YesNo ( char * ) ;
   void           Exit_YesNo ( char * ) ;
   void           Sleep ( double ) ;
   u16            Parse ( char *, u16, char * * ) ;
   char         * ToLower ( char * ) ;
   int            IsInList ( byte, char * ) ;
   char         * GetMyName ( char *, char * ) ;
   char         * GetMyHome ( char *, char * ) ;
   void           HexDump ( byte *, u16 ) ;
   double         Calibrate ( char * ) ;
   int            SlurpData ( char *, char * ) ;
   double         Palt ( double, double ) ;
   int            Cursor ( int, int ) ;
   double         Trapeziod ( int, double *, double ) ;
   double         Simpson   ( int, double *, double ) ;
   double         Taylor    ( int, double *, double ) ;
   char         * FMode ( byte ) ;
   void           Initialize ( char * ) ;
   int            FindFile ( char *, char *, char *, int ) ;

   /* small model MSC compiler won't handle this in the main */

   double         vee [ NUM_PAIRS + 12 ] ;

   u16            PrtFmt = PRT_REG ;

   char           Ver [32]  ;

   FILE         * kjherr ;          /* ver 1.25c -- set to stdout for DOS   */
                                    /*              set to stderr for unix  */

/* ------------------------------------------------------------------------ */
int main ( argc, argv )
/* ------------------------------------------------------------------------ */
  int      argc;
  char   * argv [];
/* ------------------------------------------------------------------------ */
{
   int o = 0 ;

   int i = 0 ;
   int j = 0 ;

   int      DoMSL = TRUE  ;
   byte     maxp = 0 ;

   int      OutFileUsed = 0 ;
   byte     fmode = 0 ;                               /* 0==Main, 1==Drogue */

   double   t = -4 * dT ;                             /* time interval      */

   double   acc = 0.0 ;                               /* accel == dv/dt     */
   double   vel = 0.0 ;                               /* temp accum for sum */
   double   alt = 0.0 ;                               /* another temp       */
   double   oalt = 0.0 ;                              /* Simpson() does 2dT */
   double   dalt = 0.0 ;                              /* differential alt   */

   double   ptime = 0.0 ;                             /* apogee time PAlt */
   double   atime = 0.0 ;                             /* apogee time IAlt */
   double   ftime [2] ;                               /* firing times */

   double   maxialt = 0.0 ;                           /* max inertial alt   */
   double   tmaxialt = 0.0 ;                          /* time of max i-alt  */

   double   maxpalt = 0.0 ;                           /* press alt at minvel*/

   double   maxvel = 0.0  ;
   double   tmaxvel = 0.0 ;

   double   minacc = 0.0  ;
   double   tminacc = -1.0 ;                          /* tminacc controls  */
                                                      /* derivative mode   */
   double   maxacc = 0.0  ;
   double   tmaxacc = 0.0  ;

   double   alt_0 = 0 ;                               /* launch site alt    */
   double   palt_0 = 0 ;                              /* result varb, Palt()*/
   double   palt = 0 ;                                /* result varb, Palt()*/

   double   end_of_time = TIME_MAX ;                  /* All the data (v2)  */
   int      end_t_oride = FALSE ;                     /*   or not ... (v2)  */

   byte     pre = 0;                                  /* pressure byte temp */
   byte     gee = 0 ;                                 /* tmp for AltAcc gee */

   double   oacc = 0 ;                                /* curr acceleration  */
   double   cacc = 0 ;                                /* curr acceleration  */
   double   sum  = 0 ;                                /* Gee - onegee temp  */

   int      launch = 0 ;                              /* set when sum>thold */
   int      atime_oride = 0 ;                         /* set when sum = 0   */

   double   gain = DEFAULT_GAIN ;                     /* aka slope of curve */
   double   onegee  = 0.0 ;                           /* AltAcc output @ +1 */
   double   zerogee = 0.0 ;                           /* AltAcc output @ 0G */
   double   neggee  = 0.0 ;                           /* AltAcc output @ -1 */

   double   goffset = 0.0 ;                           /* experimental ...   */

   double   goride = 0.0 ;                            /* command line slope */
   double   zoride = 0.0 ;                            /* command line 1G    */

   double   multiplier = 0.0 ;                        /* loop optomizer     */

   /* ver 1.25c print everything to stdout cause DOS can't manage stderr */

#ifdef DOS
   kjherr = stdout ;
#else
   kjherr = stderr ;
#endif

   /* get the prog name from the opsys in there -- call Name, then Home! */

   progname = GetMyName ( progname, argv [0] ) ;      /* note order!!! */
   proghome = GetMyHome ( proghome, argv [0] ) ;      /* Name then Home */

   i = FindFile ( CalFileName, proghome, CAL_NAME, R_OK ) ;
   i = FindFile ( NitFileName, proghome, NIT_NAME, R_OK ) ;

   /* initialize the data file name and output file name */

   InpFileName [ 0 ] = '\0' ;
   OutFileName [ 0 ] = '\0' ;

   /* install [[Ctrl]+[C]] handler */

   if (( signal ( SIGINT, Breaker )) == SIG_ERR )
   {
      fprintf ( kjherr, "\nprogram %s could not set Break Handler\n", progname );
      abort () ;
   }

#ifdef DOS

   /* if we own an IRQ, we own responsibility for releasing it too */

   atexit ( CleanUp ) ;

#endif

   /* go read the .nit file -- (v2) -- Moved here so CalFile, et al are set */

   Initialize ( NitFileName ) ;              /* go set the defaults    */

   /* look for command line flags */

   while ( 1 )
   {
      o = getopt ( argc, argv, "c:f:o:g:z:n:F:aqhm" ) ;

      if ( o == EOF )
        break ;

      switch (o)
      {
         case 'c':
            strncpy ( CalFileName, optarg, NAME_LEN_MAX );
            break ;

         case 'f':
            strncpy ( InpFileName, optarg, NAME_LEN_MAX );
            break ;

         case 'o':
            strncpy ( OutFileName, optarg, NAME_LEN_MAX );
            break ;

         case 'g':
            goride = atof ( optarg ) ;
            break ;

         case 'z':
            zoride = atof ( optarg ) ;
            break ;

         case 'n':
            strncpy ( NitFileName, optarg, NAME_LEN_MAX );
            break ;

         case 'F':

            if (( * optarg == 'x' ) || ( * optarg == 'X' ) ||
                ( * optarg == 'c' ) || ( * optarg == 'C' ))
                  PrtFmt = PRT_CSV ;
            else
                  PrtFmt = PRT_REG ;

            break ;

         case 'm':
            DoMSL = FALSE ;
            break ;

         case 'a':
            end_t_oride = TRUE ;
            break ;

         case 'h':
            Usage () ;
            break ;

         case 'q':
            Verbose = FALSE ;
            break ;

         case '?':
            Usage () ;
            break ;
      }
   }

   /* go read the .nit file -- watch for Overrides (v2) */

   if ( NitFileName [0] != '\0' )
   {
      Initialize ( NitFileName ) ;
   }
   /* look for a nekked file name arg out there ( ignore multi names ) */

   if ( optind < argc )
      strncpy ( InpFileName, argv [ optind ], NAME_LEN_MAX );

   /* now make sure that there __was__ an input file */

   if (( i  = SlurpData ( InpFileName, OutFileName )) != ALTACC_FILE_SIZE )
   {
      fprintf ( kjherr, "%s does not unnderstand a data file with %d bytes!\n",
                          progname, i ) ;
   }

   if (( gain = Calibrate ( CalFileName )) == 0.0 )
   {
      fprintf ( kjherr, "Calibration file %s did not have gain value!\n",
                         CalFileName ) ;
   }

   /* Version 1.25b -- moved from Calibrate () */

   if ( CaliData [OffBP].Val == 0.00 )
   {
      if ( XDucerType == MPX5100 )
         CaliData [GainBP].Val = PALT_GAIN_5100 ;
      else
         CaliData [GainBP].Val = PALT_GAIN_4100 ;

      CaliData [OffBP].Val = CaliData [ActBP].Val -
                             CaliData [GainBP].Val *
                             CaliData [AvgBP].Val ;
   }

   if ( AltAccFile.Name.Version != 0xFE )
      sprintf ( Ver, "AltAcc II - v2.%03d", AltAccFile.Name.Version );
   else
      strcpy ( Ver, "" ) ;

   if ( goride != 0.0 )
      gain = goride ;

   if ( zoride != 0.0 )
      onegee = zoride ;
   else
   {
      for ( i = 0 ; i < 4 ; i ++ )
         onegee += AltAccFile.Name.Window [i] ;

      onegee  /= 4.0 ;
   }

   zerogee = onegee - gain ;
   neggee  = zerogee - gain ;
   goffset = onegee ;

   /*   pre = ( byte ) floor ( CaliData [ AvgBP ].Val ) ; */

   /*
   if ( CaliData [ AvgBP ].Val != 0.0 )
      palt_0 = CaliData [ AvgBP ].Val ;
   else
      palt_0 = PALT_IDEAL_5100 ;
   */

   /* v1.25 */
   palt_0 = ( 29.921 - CaliData [ OffBP ].Val ) / CaliData [ GainBP ].Val ;

   alt_0   = Palt ( AltAccFile.Name.BasePre, palt_0 ) ;
   fmode   = AltAccFile.Name.BSFlags & 0x01 ;

   ftime [0] =  ( double )   AltAccFile.Name.MainSec +
                ( double ) ( AltAccFile.Name.Main16s & 0xE0 ) *  8.0 +
                ( double ) ( AltAccFile.Name.Main16s & 0x0F ) / 16.0 ;

   if ( fmode == 1 )
   {
      ftime [1] =  ( double )   AltAccFile.Name.DrogueSec +
                   ( double ) ( AltAccFile.Name.Drogue16s & 0xE0 ) *  8.0 +
                   ( double ) ( AltAccFile.Name.Drogue16s & 0x0F ) / 16.0 ;

      /*
      if ( ftime [1] > 255.9375 )
      {
         fmode = 2 ;
         ftime [1] = -1 ;
         atime = ftime [0] ;
         maxp  = AltAccFile.Name.MainPre ;
      }
      else
      { */
         atime = ftime [1] ;
         maxp  = AltAccFile.Name.DroguePre ;
/*    } */
   }
   else
   {
      ftime [1] = -1.0 ;
      atime = ftime [0] ;
      maxp  = AltAccFile.Name.MainPre ;
   }

   ptime = atime ;                                                 /* v 1.25 */

   if (( OutFileUsed = strlen ( OutFileName )) != 0 )
   {
      if (( OutFileAddr = fopen ( OutFileName, "w" )) == NULL )
      {
         fprintf ( kjherr, "\n%s cannot open output file %s\n",
                              progname, OutFileName ) ;
         exit ( 4 ) ;
      }
   }

   if ( OutFileUsed )
   {
      if ( PrtFmt == PRT_REG )
      {
         fprintf ( OutFileAddr, "%c\n", COMMENT_CHAR ) ;

         if ( Ver [0] )
            fprintf ( OutFileAddr, "%c AltAcc Firmware:          %s\n",
                      COMMENT_CHAR, Ver ) ;

         fprintf ( OutFileAddr, "%c XDucer Type (%d):          %s\n",
                   COMMENT_CHAR, XDucerType,
                                 XDucerTypeStr [XDucerType] ) ;

         fprintf ( OutFileAddr, "%c Flight Mode:              %s\n",
                   COMMENT_CHAR, FMode ( fmode )) ;
         fprintf ( OutFileAddr, "%c AltAcc Data file:         %s\n",
                   COMMENT_CHAR, InpFileName ) ;
         fprintf ( OutFileAddr, "%c Calibration file:         %s\n",
                   COMMENT_CHAR, CalFileName ) ;
         fprintf ( OutFileAddr, "%c\n", COMMENT_CHAR ) ;
         fprintf ( OutFileAddr, "%c AltAcc Gain Factor:    %11.4f GHarrys / G\n",
                   COMMENT_CHAR, gain ) ;
         fprintf ( OutFileAddr, "%c AltAcc Minus One Gee:  %11.4f GHarrys\n",
                   COMMENT_CHAR, neggee ) ;
         fprintf ( OutFileAddr, "%c AltAcc Zero Gee:       %11.4f GHarrys\n",
                   COMMENT_CHAR, zerogee ) ;
         fprintf ( OutFileAddr, "%c AltAcc Plus One Gee:   %11.4f GHarrys\n",
                   COMMENT_CHAR, onegee ) ;
         fprintf ( OutFileAddr, "%c Launch Site Pressure:  %6d      Orvilles",
                   COMMENT_CHAR, AltAccFile.Name.BasePre ) ;

         if ( CaliData [ OffBP ].Val != 0.00 )
         {
            fprintf ( OutFileAddr, " ( %.2f in Hg )\n",
                      AltAccFile.Name.BasePre *
                      CaliData [ GainBP ].Val +
                      CaliData [ OffBP ].Val ) ;
         }
         else
            fprintf ( OutFileAddr, "\n" ) ;

         fprintf ( OutFileAddr, "%c Launch Site Altitude:  %6.0f      %s MSL\n",
                   COMMENT_CHAR,
                   alt_0, Units [ U[0]] ) ;

                   /* v1.25
                   alt_0 + CaliData [ ActAlt ].Val, Units [ U[0]] ) ;
                    */

         fprintf ( OutFileAddr, "%c\n", COMMENT_CHAR ) ;

         if ( fmode == 1 )
         {
            fprintf ( OutFileAddr,
                     "%c Drogue Fired at Time:  %11.4f %s      ( %6.0f %s AGL )\n",
                      COMMENT_CHAR, ftime [1], Units [ U[ 2 ]],
                      Palt ( AltAccFile.Name.DroguePre, AltAccFile.Name.BasePre ),
                      Units [ U[0]] ) ;
         }
         fprintf ( OutFileAddr,
                  "%c Main Fired at Time:    %11.4f %s      ( %6.0f %s AGL )\n",
                   COMMENT_CHAR, ftime [0], Units [ U[ 2 ]],
                   Palt ( AltAccFile.Name.MainPre, AltAccFile.Name.BasePre ),
                   Units [ U[0]] ) ;

         fprintf ( OutFileAddr, "%c\n", COMMENT_CHAR ) ;
         fprintf ( OutFileAddr, "%c\n", COMMENT_CHAR ) ;

         for ( i = 0 ; i < NUM_HEADER ; i ++ )
            fprintf ( OutFileAddr, "%c %s\n", COMMENT_CHAR, Header [i] ) ;

      }
      else
      {
         for ( i = 0 ; i < NUM_EXHEAD ; i ++ )
            fprintf ( OutFileAddr, "%s\n", ExHead [i] ) ;
      }
   }

   if ( Verbose )
   {
      if ( Ver [0] )
         fprintf ( kjherr, "AltAcc Firmware:             %s\n", Ver ) ;

      fprintf ( kjherr, "XDucer Type (%d):             %s\n",
                 XDucerType, XDucerTypeStr [XDucerType] ) ;

      fprintf ( kjherr, "Flight Mode:                 %s\n",
                FMode ( fmode )) ;
      fprintf ( kjherr, "AltAcc Gain Factor:       %11.4f GHarrys / G\n",
                gain ) ;
      fprintf ( kjherr, "AltAcc Minus One Gee:     %11.4f GHarrys\n",
                neggee ) ;
      fprintf ( kjherr, "AltAcc Zero Gee:          %11.4f GHarrys\n",
                zerogee ) ;
      fprintf ( kjherr, "AltAcc Plus One Gee:      %11.4f GHarrys\n",
                onegee ) ;

      fprintf ( kjherr, "Launch Site Pressure:     %6d      Orvilles",
                AltAccFile.Name.BasePre ) ;

      if ( CaliData [ GainBP ].Val != 0.00 )
      {
         fprintf ( kjherr, " ( %.2f in Hg )\n",
                   AltAccFile.Name.BasePre *
                   CaliData [ GainBP ].Val +
                   CaliData [ OffBP ].Val ) ;
      }
      else
         fprintf ( kjherr, "\n" ) ;

      fprintf ( kjherr, "Launch Site Altitude:     %6.0f      %s MSL\n",
                alt_0, Units [ U[0]] ) ;

               /* v1.25
                alt_0  + CaliData [ ActAlt ].Val, Units [ U[0]] ) ;
                */

      fprintf ( kjherr, "\n" ) ;

      if ( fmode == 1 )
      {
         fprintf ( kjherr,
                  "Drogue Fired at Time:     %11.4f %s      ( %6.0f %s AGL )\n",
                   ftime [1], Units [ U[2]],
                   Palt ( AltAccFile.Name.DroguePre, AltAccFile.Name.BasePre ),
                   Units [ U[0]] ) ;
      }
      fprintf ( kjherr,
               "Main Fired at Time:       %11.4f %s      ( %6.0f %s AGL )\n",
                ftime [0], Units [ U[ 2 ]],
                Palt ( AltAccFile.Name.MainPre, AltAccFile.Name.BasePre ),
                Units [ U[0]] ) ;
   }

   /* I want to use Simpson's rule for altitude and Taylor's 2nd order
    * 2-step derivative to back acceleration from velocity.  The simple
    * way is to precalc the velocity into an array then work with that.
    * Velocity is computed using the trapezoidal rule cause the data is
    * noisy anyway. Here we go ...
    */

   /* Fill the velocity array ... pad 2 then do Countdown data, watch j !! */

   for ( j = 0 ; j < 6 ; j ++ )
      vee [ j ] = 0.0 ;

   oacc = 0.0 ;                     /* last accel reading for Trapeziod () */
   vel  = 0.0 ;                     /* Sum of Accel == Velocity == vel */

   multiplier = dT * GEE / gain / 2.0 ;   /* replace slow Trap () w/ inline */

   /* oldest, older, old, cur acceleration go in next ... watch j !! */

   for ( i = 0 ; i < 4 ; i ++ )
   {
      cacc       = AltAccFile.Name.NitAcc [i] - onegee ;
      vel       += ( oacc + cacc ) * multiplier ;
      vee [j++]  = vel ;

      oacc = cacc ;
   }

   /* Now do the flight data ... still using j !!!  */

   for ( i = 0 ; i < NUM_PAIRS ; i ++ )
   {
      cacc       = AltAccFile.Name.Data [i].A - onegee ;
      vel       += ( oacc + cacc ) * multiplier ;
      vee [j++]  = vel ;

      if ( AltAccFile.Name.Data [i].P == 254 )
         break ;

      oacc = cacc ;

   }

   /* Finally,  pad the end with zeros for Taylor () */

   vee [ j++ ] = 0.0 ;
   vee [ j ]   = 0.0 ;

   j = 0 ;

   o = AltAccFile.Name.WinPtr ;

   acc  = 0.0 ;
   alt  = 0.0 ;
   oalt = 0.0 ;
   sum  = 0.0 ;

   for ( i = 2 ; i < NUM_PAIRS + 6 ; i++ )
   {
      if (( t == ftime [0] ) || ( t == ftime [1] ))
         t += dT * 4 ;
      else
         t += dT ;

      if ( j > 7 )
      {
         gee  = AltAccFile.Name.Data [j-8].A ;
         pre  = AltAccFile.Name.Data [j-8].P ;
      }
      else if ( j > 5 )
      {
         gee  = AltAccFile.Name.NitAcc [j-4] ;
         pre  = AltAccFile.Name.LastPre ;
      }
      else if ( j > 3 )
      {
         gee  = AltAccFile.Name.NitAcc [j-4] ;
         pre  = AltAccFile.Name.BasePre ;
      }
      else
      {
         o = Cursor ( o + 1, 4 ) ;
         gee = AltAccFile.Name.Window [ o ] ;
         pre = AltAccFile.Name.BasePre ;
      }

      if (( pre == 254 ) || ( t > end_of_time ))
         break ;

      if ( j > 3 )
      {
         dalt = Simpson ( i, vee, dT_3 ) - oalt ;
         alt += dalt ;
         acc  = Taylor  ( i, vee, TWELVE_dT ) ;
         sum += ( gee - goffset ) ;
         oalt = dalt ;

         if (( launch == 0 ) && ( sum > LAUNCH_THOLD ))            /* v 1.25 */
            launch = 1 ;

         if ( launch  && ( sum <= 0.0 ) && ( atime_oride == 0 ))   /* v 1.25 */
         {
            atime = t ;
            atime_oride = 1 ;
         }
      }

      palt = Palt ( pre, AltAccFile.Name.BasePre ) ;

      if ( t <= atime )
      {
         /* v 1.25 */

         if ( pre <= maxp )
         {
            maxp = pre ;
            ptime = t ;
         }
         if ( alt > maxialt )
         {
            maxialt = alt ;
            tmaxialt = t ;
         }
         if ( vee [i] > maxvel )
         {
            maxvel = vee [i] ;
            tmaxvel = t ;
         }

      /* if ( t < atime ) */
         if ( sum >= 0.0 )                                         /* v 1.25 */
         {
            if ( acc < minacc )
            {
            minacc = acc ;
            tminacc = t ;
            }
            if ( acc > maxacc )
            {
               maxacc = acc ;
               tmaxacc = t ;
            }
         }
      }
      else
      {
         /* (v2) -- Break early if we get back to the ground */

         if (( end_t_oride == FALSE ) &&
             ( pre >= AltAccFile.Name.BasePre ) &&
             ( end_of_time == TIME_MAX ))
         {
            end_of_time = t + TIME_END ;
         }
      }

      if ( OutFileUsed )
      {
         if ( PrtFmt == PRT_REG )
         {
            fprintf ( OutFileAddr, "  %10.5f    %3d    %3d  %5.0f",
                                        t,
                                        gee,
                                        pre,
                                        sum ) ;

            fprintf ( OutFileAddr, "  %9.2f  %9.2f  %9.2f",
                                       acc,
                                       vee [i],
                                       alt ) ;

            fprintf ( OutFileAddr, "  %8.0f\n", palt ) ;
         }
         else
         {
            fprintf ( OutFileAddr, "%.4f,%d,%d,%.0f,",
                                        t,
                                        gee,
                                        pre,
                                        sum ) ;

            if ( t <= atime )
            {
               fprintf ( OutFileAddr, "%.2f,%.2f,%.2f,",
                                       acc,
                                       vee [i],
                                       alt ) ;
            }
            else
            {
               fprintf ( OutFileAddr, ",,," ) ;
            }

            fprintf ( OutFileAddr, "%.0f\n", palt ) ;

         }
      }

      j ++ ;

   }

   maxpalt = Palt ( maxp, AltAccFile.Name.BasePre ) ;

   fprintf ( kjherr, "\n" ) ;

   if ( DoMSL )
   {
      fprintf ( kjherr,
               "MSL Pressure Altitude:    %6.0f    %s         ( %9.5f sec )\n",
               Palt ( maxp, palt_0 ) - alt_0, Units [ U[ 0 ]], ptime );
   }
   fprintf ( kjherr,
            "AGL Pressure Altitude:    %6.0f    %s         ( %9.5f sec )\n",
             maxpalt, Units [ U[ 0 ]], ptime );
   fprintf ( kjherr,
            "Max Inertial Altitude:    %6.0f    %s         ( %9.5f sec )\n",
             maxialt, Units [ U[ 0 ]], tmaxialt );
   fprintf ( kjherr,
            "Maximum Velocity:         %8.1f  %s / %s   ( %9.5f sec )\n",
             maxvel, Units [ U[ 0 ]], Units [ U[ 2 ]], tmaxvel );
   fprintf ( kjherr,
            "Maximum Acceleration:     %9.2f %s / %s^2 ( %9.5f sec, %5.1f G's )\n",
             maxacc, Units [ U[ 0 ]], Units [ U[ 2 ]],
             tmaxacc, maxacc/GEE ) ;
   fprintf ( kjherr,
            "Minimum Acceleration:     %9.2f %s / %s^2 ( %9.5f sec, %5.1f G's )\n",
             minacc, Units [ U[ 0 ]], Units [ U[ 2 ]],
             tminacc, minacc/GEE );

   if ( OutFileUsed )
   {
      if ( PrtFmt == PRT_REG )
      {

      fprintf ( OutFileAddr, "%c\n",
                COMMENT_CHAR ) ;

      if ( DoMSL )
      {
         fprintf ( OutFileAddr,
                  "%c MSL Pressure Altitude: %6.0f    %s         ( %9.5f sec )\n",
                  COMMENT_CHAR,
                  Palt ( maxp, palt_0 ) - alt_0, Units [ U[ 0 ]], ptime );
      }
      fprintf ( OutFileAddr,
               "%c AGL Pressure Altitude: %6.0f    %s         ( %9.5f sec )\n",
                COMMENT_CHAR, maxpalt, Units [ U[ 0 ]], ptime );
      fprintf ( OutFileAddr,
               "%c Max Inertial Altitude: %6.0f    %s         ( %9.5f sec )\n",
                COMMENT_CHAR, maxialt, Units [ U[ 0 ]], tmaxialt );
      fprintf ( OutFileAddr,
               "%c Maximum Velocity:      %8.1f  %s / %s   ( %9.5f sec )\n",
                COMMENT_CHAR, maxvel, Units [ U[ 0 ]],
                Units [ U[ 2 ]], tmaxvel );
      fprintf ( OutFileAddr,
               "%c Maximum Acceleration:  %9.2f %s / %s^2 ( %9.5f sec, %5.1f G's )\n",
                COMMENT_CHAR, maxacc, Units [ U[ 0 ]],
                Units [ U[ 2 ]], tmaxacc, maxacc/GEE ) ;
      fprintf ( OutFileAddr,
               "%c Minimum Acceleration:  %9.2f %s / %s^2 ( %9.5f sec, %5.1f G's )\n",
                COMMENT_CHAR, minacc, Units [ U[ 0 ]],
                Units [ U[ 2 ]], tminacc, minacc/GEE );
      }

      fclose ( OutFileAddr ) ;
   }

   exit ( 0 ) ;

}
/* ------------------------------------------------------------------------ */
void  Usage ()
/* ------------------------------------------------------------------------ */
{
   fprintf ( kjherr, "%s (v%s) -- AltAcc data reduction program\n",
             progname, VERSION ) ;
   fprintf ( kjherr, "Usage:  %s [options] FILE\n", progname );
   fprintf ( kjherr, "options include:\n" );
   fprintf ( kjherr, "        -c FILE -> Calibration File produced by probate\n" );
   fprintf ( kjherr, "        -f FILE -> AltAcc data file produced by proread\n" );
   fprintf ( kjherr, "        -n FILE -> Override default init file prodata.nit with FILE\n" );
   fprintf ( kjherr, "        -o FILE -> Output file for produce results\n" );
   fprintf ( kjherr, "        -z VAL  -> One Gee Override Value ( Overrides Cal File One Gee )\n" );
   fprintf ( kjherr, "        -g VAL  -> Gain Override ( Overrides Cal File Gain Factor )\n" );
   fprintf ( kjherr, "        -F FMT  -> if FMT = c or C or x or X then print comma\n" );
   fprintf ( kjherr, "                   separated values ( ala an Xcel csv file )\n" );
   fprintf ( kjherr, "                   Otherwise print a table of data with headers (default)\n" );
/* fprintf ( kjherr, "        -m      -> Output BOTH MSL pressure alt AND AGL pressure alt\n" ); */
   fprintf ( kjherr, "        -m      -> Do NOT show MSL pressure alt with AGL pressure alt\n" );
   fprintf ( kjherr, "        -a      -> Force all the data out, even after touchdown\n" );
   fprintf ( kjherr, "        -q      -> be quiet about it\n" );
   fprintf ( kjherr, "        -h      -> help ( this list )\n" );
   fprintf ( kjherr, "           FILE -> FILE == AltAcc data file produced by proread\n" );
   fprintf ( kjherr, "                           ( same effect as the -f FILE option )\n" );

   exit ( 6 ) ;
}
/* ------------------------------------------------------------------------ */
void   CleanUp ()
/* ------------------------------------------------------------------------ */
{
   /* atexit was exec'd after we took the [Ctrl][Break] IRQ ... so ...      */

   signal ( SIGINT, SIG_IGN );          /* let dos do whatever it do        */
}
/* ------------------------------------------------------------------------ */
void  Breaker ( sig )
/* ------------------------------------------------------------------------ */
      int   sig ;
/* ------------------------------------------------------------------------ */
{
   /* A signal handler must take a single argument. The argument can be
    * tested within the handler and thus allows a single signal handler
    * to handle several different signals. In this case, the parameter
    * is included to keep the compiler from generating a warning but is
    * ignored because this signal handler only handles one interrupt:
    * SIGINT (Ctrl+C).
    */

   /* Disallow CTRL+C during handler. */

   signal ( SIGINT, SIG_IGN );

   Exit_YesNo ( "Break Detected - abort processing (y|n)? " );

   /* The CTRL+C interrupt must be reset to our handler since
    * by default it is reset to the system handler.
    */

   signal ( SIGINT, Breaker );
}
/* ------------------------------------------------------------------------ */
void   SafeOut ( str )         /* Outputs a string using system level calls. */
/* ------------------------------------------------------------------------ */
      char *str ;
/* ------------------------------------------------------------------------ */
{
   fputs ( str, stdout ) ;
}
/* ------------------------------------------------------------------------ */
int   SafeIn ()             /* Inputs a character using system level calls. */
/* ------------------------------------------------------------------------ */
{
   return ( fgetc ( stdin )) ;
}
/* ------------------------------------------------------------------------ */
char  YesNo ( Mess )
/* ------------------------------------------------------------------------ */
      char * Mess   ;
/* ------------------------------------------------------------------------ */
{
   int  c ;
   char str [] = " " ;

   SafeOut ( Mess );                    /* ask dos to dump the message */

   c = SafeIn ();                       /* ask dos for an input char   */
   str [0] = c;                         /* make a string out of it ... */
   SafeOut ( str );                      /* and ask dos to dump it      */
   SafeOut ( "\r\n" );

   if ( isupper ( c ))
      c = tolower ( c ) ;

   return ( c ) ;
}
/* ------------------------------------------------------------------------ */
void   Exit_YesNo ( Mess )
/* ------------------------------------------------------------------------ */
      char * Mess   ;
/* ------------------------------------------------------------------------ */
{
   if ( YesNo ( Mess ) == 'y' )
      exit ( 3 ) ;
}
/* ------------------------------------------------------------------------ */
void Sleep ( wait )
/* ------------------------------------------------------------------------ */
     double   wait ;
/* ------------------------------------------------------------------------ */
{
    time_t start, goal ;

    time ( & start ) ;

    do
    {
        time ( & goal ) ;

    } while (( difftime ( goal, start )) < wait ) ;
}
/* ------------------------------------------------------------------------ */
u16   Parse (line, maxarg, word)
/* ------------------------------------------------------------------------ */
      char * line;
      u16    maxarg;
      char * word [];
/* ------------------------------------------------------------------------ */

{
   u16      i = 0;
   char   * j = line + strlen (line);

   while (( line < j ) && ( i < maxarg ))
   {
      while (( line < j ) && ( isspace ( *line )))
         line++ ;

      if (( line >= j ) || ( *line == COMMENT_CHAR ))
         break;

      word [ i++ ] = line;

      while (( line < j ) && !( isspace ( *line )))
         line++ ;

      if ( line >= j )
         break;

      *line++ = '\0';
  }

  return ( i ) ;

}

/* ------------------------------------------------------------------------ */
char  * ToLower ( InStr )
/* ------------------------------------------------------------------------ */
      char * InStr ;
/* ------------------------------------------------------------------------ */
{
   u16   i = 0 ;

   while ( i < strlen ( InStr ))
   {
      if ( isupper ( InStr [ i ] ))
         InStr [ i ]  = tolower ( InStr [ i ] ) ;

      i ++ ;
   }

   return ( InStr ) ;

}
/* ------------------------------------------------------------------------ */
char  * GetMyName ( Name,  ArgV )
/* ------------------------------------------------------------------------ */
      char * Name ;
      char * ArgV ;
/* ------------------------------------------------------------------------ */
{
   /* Throw out the path */

   if (( Name = strrchr ( ArgV, DIR_SEP )) != NULL )
   {
      * Name = '\0' ;                  /* delimit the path from the name */
        Name++;
   }
   else
      Name = ArgV ;

#ifdef DOS

   /* throw away the '.exe' */

   if (( p = strrchr ( Name, '.' )) != NULL )
      * p = '\0' ;

#endif

   return ( ToLower ( Name )) ;

}
/* ------------------------------------------------------------------------ */
int  IsInList ( Char, List )
/* ------------------------------------------------------------------------ */
      byte   Char ;
      char * List ;
/* ------------------------------------------------------------------------ */
{
   int i = 0 ;

   for ( i = 0 ; i < strlen ( List ) ; i ++ )
      if ( Char == List [i] )
         return ( 1 ) ;

   return ( 0 ) ;
}
/* ------------------------------------------------------------------------ */
char  * GetMyHome ( Path,  ArgV )
/* ------------------------------------------------------------------------ */
      char * Path ;
      char * ArgV ;
/* ------------------------------------------------------------------------ */
{
   char * p ;
   int    i = 0 ;
   int    j = 0 ;

   /* First look for a Home for the System Environment */

   if (( p = getenv ( "PRODATA" )) != NULL )
      return ( p ) ;

   /* None found, try for a fqpn */

   Path = ArgV ;

   p = ArgV + strlen ( ArgV ) - 1;

   while ( p >= Path )
   {
      if ( IsInList ( * p, "/\\" ))
         * p = '\0' ;
      else
         break ;

      p -- ;
   }

   /* strip off /..'s  and count the occurances */

   while ( 1 )
   {
      i = strlen ( Path ) - 1 ;

      if (( i > 1 ) && ( Path [i] == '.' ) &&
                       ( Path [i-1] == '.' ) &&
                       ( Path [i-2] == DIR_SEP ))
      {
         Path [i-2] = '\0' ;
         j ++ ;
      }
      else
         break ;
   }

   /* now trim the corresponding dir's  */

   i = 0 ;

   while ( i < j )
   {
      if (( p = strrchr ( Path, DIR_SEP )) != NULL )
            * p = '\0' ;
      i ++ ;
   }

   /* a unix system puts the program name in the env sans path, so ... */

   if ( strcmp ( Path, progname ) != 0 )
      return ( ToLower ( Path )) ;
   else
      return ( "." ) ;

}
/* ------------------------------------------------------------------------ */
void  HexDump ( Pointer, Length )
/* ------------------------------------------------------------------------ */
      byte * Pointer ;
      u16    Length ;
/* ------------------------------------------------------------------------ */
{
   u16   i = 0 ;
   u16   j = 0 ;

   for ( i = 0 ; i < Length ; i ++ )
   {
      if (( i % 16 ) == 0 )
         fprintf ( kjherr, "%04x    ", i ) ;

      fprintf ( kjherr, "%02x ", Pointer [ i ] ) ;

      if (( i % 16 ) == 7 )
         fprintf ( kjherr, " " ) ;

      if (( i % 16 ) == 15 )
      {
         fprintf ( kjherr, "    " ) ;

         for ( j = i-15 ; j <=i ; j ++ )
         {
            if ( isprint ( Pointer [ j ] ))
               fprintf ( kjherr, "%c", Pointer [ j ] ) ;
            else
               fprintf ( kjherr, "." ) ;
         }
         fprintf ( kjherr, "\n" ) ;
      }

      if (( i % 320 ) == 319 )
         if (( YesNo ( "\n[More] Press q to quit " )) == 'q' )
            break ;

   }

}
/* ------------------------------------------------------------------------ */
double   Calibrate ( char * CalFile )
/* ------------------------------------------------------------------------ */
{
   FILE * CalFilePtr ;

   u16   i = 0 ;

   char     InpBuf [ INP_SIZE+1 ] ;
   char  *  ArgBuf [ MAXARG ] ;

   if ( Verbose )
      fprintf ( kjherr, "opening calibration file     %s\n", CalFile ) ;

   if (( CalFilePtr = fopen ( CalFile, "r" )) == NULL )
   {
      fprintf ( kjherr, "%s cannot open calibration file %s for input\n",
                          progname, CalFile ) ;
      exit ( 4 ) ;
   }

   while ( ! feof ( CalFilePtr ))
   {
      if ( fgets ( InpBuf, INP_SIZE, CalFilePtr ) != NULL )
      {
         if ( Parse ( InpBuf, MAXARG, ArgBuf ) > 1 )
         {
            for ( i = 0 ; i < NUM_CAL_ROWS ; i ++ )
               if ( strcmp ( CaliData [i].Tag, ToLower ( ArgBuf [ 0 ] )) == 0 )
                  break ;

            if ( i < NUM_CAL_ROWS )
               CaliData [i].Val = atof ( ArgBuf [ 1 ] ) ;
         }
      }
   }

   fclose ( CalFilePtr ) ;

   /* Version 1.25 -- use the offset from the .cal file so actbp is on */

   if ( CaliData [XDucer].Val == 5100.0 )
      XDucerType = MPX5100 ;
   else if ( CaliData [XDucer].Val == 4100.0 )
      XDucerType = MPX4100 ;

   return ( CaliData [ Slope ].Val );

}
/*--------------------------------------------------------------------------*/
double  Palt ( Press, Press_0 )
/*--------------------------------------------------------------------------*/
      double Press   ;
      double Press_0 ;
/*--------------------------------------------------------------------------*/
{
   double   Alt ;
   double   ln_dP ;
   double   dP ;

   double   P0 ;
   double   P1 ;

   if ( Press <= 0 )
      return ( HUGE_VAL ) ;

   /* The Motorolla data sheet sez 4.5 V / 14.5 PSI which implies 4.56 V
    * at 14.7 PSI.  The unit output is 209 / 14.7 while the ideal is
    * 229.5 at 14.5 ( assume 255 / 5 Unit / volt ).  This means the
    * readings are offset low 23.3 units.  PALT_OFFSET is hardcoded
    * for now to +23.3 and all readings are adjusted up by this value.
    */

   if ( CaliData [ OffBP ].Val != 1.00 )
   {
      P0 = Press_0 * CaliData [ GainBP ].Val + CaliData [ OffBP ].Val ;
      P1 = Press   * CaliData [ GainBP ].Val + CaliData [ OffBP ].Val ;
      dP = P1 / P0 ;
   }
   else
   {
      dP = (( Press   + CaliData [ OffBP ].Val )  /
            ( Press_0 + CaliData [ OffBP ].Val )) ;
   }

   ln_dP = log ( dP ) ;

   Alt = ( 1 - exp ( ln_dP / 5.2556 )) / 0.00000688 ;

   return ( Alt ) ;
}
/*--------------------------------------------------------------------------*/
int   Cursor ( where, size )
/*--------------------------------------------------------------------------*/
      int   where ;
      int   size ;
/*--------------------------------------------------------------------------*/
{
   return ( where % size ) ;
}
/*--------------------------------------------------------------------------*/
double   Trapeziod ( ptr, array, dt )
/*--------------------------------------------------------------------------*/
         int      ptr ;
         double * array ;
         double   dt ;
/*--------------------------------------------------------------------------*/
{
   /* I tried Simpson's rule but the noise in the accelerometer output made
    * the output less accurate than a simple trapezoid integral.  This also
    * made the 3-element array for Altitude ( s[] ) moot but it is easier
    * to leave it than to rewrite the code :-( since removed )-:
    */

   double   retval =  0 ;

   retval  = ( array [ptr-1] + array [ptr] ) / 2.0 ;

   return ( retval * dt ) ;

}
/*--------------------------------------------------------------------------*/
double   Simpson ( ptr, array, dt )
/*--------------------------------------------------------------------------*/
         int      ptr ;
         double * array ;
         double   dt ;
/*--------------------------------------------------------------------------*/
{
   double   retval =  0 ;

   /* dt is actually dt / 3 here */

   retval  = dt * ( array [ptr-1] + 4 * array [ptr]  + array [ ptr+1 ] ) ;

   return ( retval ) ;

}
/*--------------------------------------------------------------------------*/
double   Taylor ( ptr, array, dt )
/*--------------------------------------------------------------------------*/
         int      ptr ;
         double * array ;
         double   dt ;
/*--------------------------------------------------------------------------*/
{
   double   retval =  0 ;

   /* dt is actually dt * 12 here !!! */

   retval  = ( array [ptr-2] - 8 * array [ptr-1] +
                               8 * array [ptr+1] - array [ptr+2] ) / dt ;

   return ( retval ) ;

}
/* ------------------------------------------------------------------------ */
char  * FMode ( fmode )
/* ------------------------------------------------------------------------ */
      byte   fmode ;
/* ------------------------------------------------------------------------ */
{
   switch ( fmode )
   {
      case 0 :
         return ( "Main Only Mode" );
      case 1 :
         return ( "Drogue to Main Mode" ) ;
      case 2 :
         return ( "Drogue to Main Mode -- !! No Drogue Fire !!" ) ;
   }
   return ( "" ) ;
}
/* ------------------------------------------------------------------------ */
void  Initialize ( char * NitFile )
/* ------------------------------------------------------------------------ */
{
   u16   i = 0 ;

   char     InpBuf [ INP_SIZE+1 ] ;
   char  *  ArgBuf [ MAXARG ] ;

   FILE *   NitAddr ;

   if ( NitFile [0] == '\0' )
      return ;

   if (( NitAddr = fopen ( NitFile, "rb" )) == NULL )
   {
      fprintf ( kjherr, "\n%s cannot open initialization file %s for input\n",
                           progname, NitFileName ) ;
   }
   else
   {
      while ( ! feof ( NitAddr ))
      {
         if ( fgets ( InpBuf, INP_SIZE, NitAddr ) != NULL )
         {
            if ( Parse ( InpBuf, MAXARG, ArgBuf ) > 1 )
            {
               ToLower ( ArgBuf [0] ) ;

               for ( i = 0 ; i < NUM_NIT_TAGS ; i ++ )
               {
                  if ( strcmp ( NitTags [i].Tag, ArgBuf [0] ) == 0 )
                  {
                     switch ( NitTags [i].Ptr )
                     {
                        case NT_PORT:

                           if ( ! ComOride )
                              strncpy ( ComFileName, ArgBuf [1], NAME_LEN_MAX );

                           break ;

                        case NT_CAL:

                           strncpy ( CalFileName, ArgBuf [1], NAME_LEN_MAX );
                           break ;

                        case NT_XDUCER :

                           /* v1.25b oops ... */

                           if ( strcmp ( ArgBuf [1], "5100" ) == 0 )
                           {
                              XDucerType = MPX5100 ;
                           }
                           else if ( strcmp ( ArgBuf [1], "4100" ) == 0 )
                           {
                              XDucerType = MPX4100 ;
                           }
                           else
                           {
                              fprintf ( kjherr, "Unknown XDucer Type: %s\n",
                                          ArgBuf [1] );

                              XDucerType = MPX4100 ;
                           }

                           break ;

                        default:
                           break ;
                     }
                     break ;
                  }
               }
            }
         }
      }
      fclose ( NitAddr ) ;
   }

   NitFile [0] = '\0' ;                       /* This is for the -n arg */

   /*
   CaliData [ GainBP ].Val = PALT_GAIN_4100   ;
   CaliData [ OffBP ].Val  = PALT_OFFSET_4100 ;
   */
}
/* ------------------------------------------------------------------------ */
int SlurpData ( char * InpFile, char * OutFile )
/* ------------------------------------------------------------------------ */
{

   FILE * InpPtr ;

   int BytesRead = 0 ;

   if ( strlen ( InpFile ) == 0 )
      Usage () ;
   else
   {
      /* make sure input file != output file */

      if ( strcmp ( InpFile, OutFile ) == 0 )
      {
         fprintf ( kjherr,
                  "\n%s will simply NOT overwrite your input file!\n",
                   progname ) ;

         exit ( 4 ) ;
      }

      /* can we open the inp file ? */

      if (( InpPtr = fopen ( InpFile, "rb" )) == NULL )
      {
         fprintf ( kjherr, "\n%s cannot open data file %s for input\n",
                   progname,
                   InpFile ) ;
         exit ( 4 ) ;
      }
   }

   /* slurp the data into the buffer union */

   BytesRead = fread ( & AltAccFile.Byte [0], sizeof ( byte ),
                         ALTACC_FILE_SIZE,    InpPtr ) ;

   if ( Verbose )
   {
      fprintf ( kjherr, "read %d bytes from         %s\n",
                BytesRead,
                InpFile );
   }

   /* close the input file */

   fclose ( InpPtr ) ;

   return ( BytesRead ) ;
}
/* ------------------------------------------------------------------------ */
int FindFile ( char * FileBuf, char * HomeDir, char * WhatName, int Mode )
/* ------------------------------------------------------------------------ */
{

   /* look for a file:  if not here then in $PRODATA */

   sprintf ( FileBuf, "%s%c%s", ".", DIR_SEP, WhatName ) ;

   if ( access ( FileBuf, Mode ) == 0 )
      return ( 1 ) ;

   sprintf ( FileBuf, "%s%c%s", HomeDir, DIR_SEP, WhatName ) ;

   if ( access ( FileBuf, Mode ) == 0 )
      return ( 1 ) ;

   return ( 0 ) ;
}

