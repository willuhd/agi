# 26-27 Course Catalog — COMPLETE Master Extract (for scheduling optimizer)
**CORRECTION (owner ruling): `.gpa` "weight" is a GPA CREDIT multiplier, not
contact time. Load values in this file that cite `.gpa` as authority are
GPA credits, NOT periods/week. For scheduling, ONLY catalog-prose loads
(~16 entries: Econ/Business/Psych/WorldLang + G9 M2/M3 forms) and observed
grid slots are time quantities. `src/config/courses.toml` is the corrected
machine-readable load table.**
Source: `catalog_full.txt` (pypdf, PDF pp.0-107) + `26-27-catalog-raw/*.webp` vision spot-checks (34,72,13,14) + `catalog_extract.md` (prior partial; corrected — see §5).
Legend: Load = GPA-credit weight from Courses.gpa (Spring 2026 v3.4, repo-owner ground truth) — BOLD = .gpa weight; `*` = .gpa covers G9/10/11AP/IB/A-Level bands (multi-grade rows take covered band); `n/s¹²` = no .gpa band (G12-only) and catalog silent (catalog value appended as `(cat: …)` where prose states one); plain `n/s` = neither source states a load (optionals/PE/co-curric/electives); `~` = band-inferred. Dur: Y=year, 2Y=two-year, Sem=semester. Mod = module (M1-M4, G9-M2/M3). Codes literal from catalog (spacing normalized only).
Counts: 230 course-rows; 165 with .gpa loads; 25 n/s¹² (G12-only, no .gpa band); 40 optionals/PE/co-curric/electives (catalog-kept or n/s). No clock times, no period lengths, no max class caps anywhere.

## MASTER TABLE
### Chinese (16)
| Course | Code | Gr | Dur | Load | Mod | Pre-req / gate | Venue | Shared / no-repeat |
|---|---|---|---|---|---|---|---|---|
| Chinese Beginner | CH010Eooo/CH012Eooo | 10,12 | 1Y | **3.0*** | core | None | n/s | G10+G12 mixed intake |
| Chinese Level I Lang+Cult | CHl009Eoo1/010/011/012 | 9-12 | 2Y | **3.0*** | core | None | n/s | cross-grade shared (2Y span) |
| Chinese Level II Lang+Cult | CHl009Eoo2/010/011/012 | 9-12 | 2Y | **3.0*** | core | Level I or equiv | n/s | cross-grade shared |
| Chinese Level III Lang+Cult | CHl009Eoo3/010/011/012 | 9-12 | 2Y | **3.0*** | core | Level II or equiv (500hrs non-native) | n/s | cross-grade shared |
| Chinese Level IV Lang+Cult | CHl009Eoo4/010/011/012 | 9-12 | 2Y | **3.0*** | core | Level III or equiv (600 periods) | n/s | cross-grade shared |
| Chinese Level V Lang+Cult | CHl009Eoo5/010/011/012 | 9-12 | 2Y | **3.0*** | core | Level IV or equiv (800hrs) | n/s | cross-grade shared |
| Chinese Level VI Lang+Cult | CHl009Eoo6/010/011/012 | 9-12 | 2Y | **3.0*** | core | Level V or equiv (1000hrs) | n/s | cross-grade shared |
| Chinese Level VII Lang+Cult | CHl011Eoo7/012Eoo7 | 11-12 | 2Y | **3.0*** | core | Level VI in G10 or equiv | n/s | cross-grade shared |
| Chinese Level VIII Lang+Comp | CHl009Eno/010/011/012Eno/110 | 9-12 | 1Y | **3.0*** | core | prev yr (chain) | n/s | feeds IB Chinese B HL |
| Chinese Level IX Lang+Lit | CHl009E120/010/011/012 | 9-12 | 1Y | **3.0*** | core | prev yr (chain) | n/s | feeds IB Chinese A |
| Chinese Level X Literature | CHl009E130/010/011/012 | 9-12 | 1Y | **3.0*** | core | Level IX prev yr | n/s | feeds IB Chinese A |
| AP Chinese Lang+Cult | CHl010E170 | 10 | 1Y | **3.0** | core/AP | Chinese V/VI/VIII in G9; external AP exam mandatory | n/s | feeds IB Acquisition Mandarin |
| IB Acquisition Mandarin SL | CHl011E160/012E160 | 11-12 | 2Y | **6.0** | IB (indep sched) | Level V/VI or AP Chinese in G10; IB exam Y2 | n/s | SL/HL same code family |
| IB Acquisition Mandarin HL | CHl011E160/012E160 | 11-12 | 2Y | **6.0** | IB (indep sched) | Level VIII or AP Chinese in G10; IB exam Y2 | n/s | SL/HL same code family |
| IB Chinese Lang+Lit (A) | CHl011E160/012E160 | 11-12 | 2Y | **6.0** | IB (indep sched) | Level IX in G10; IB exam Y2 | n/s | — |
| IB Chinese Literature (A) | CHl011E160/012E160 | 11-12 | 2Y | **6.0** | IB (indep sched) | Level IX in G10; IB exam Y2 | n/s | — |

### English (22)
| Course | Code | Gr | Dur | Load | Mod | Pre-req / gate | Venue | Shared / no-repeat |
|---|---|---|---|---|---|---|---|---|
| Survey Western Lit I S | ENG009S110 | 9 | 1Y | **6.0** | core | Eng 8S or equiv | n/s | — |
| Survey Western Lit I S+ | ENG009S120 | 9 | 1Y | **6.0** | core | Eng 8S+ or equiv | n/s | — |
| Survey Western Lit I H | ENG009F130 | 9 | 1Y | **6.0** | core | Eng 8H or equiv | n/s | — |
| Survey Western Lit I H+ | ENG009F131 | 9 | 1Y | **6.0** | core | Eng 8H+ or equiv | n/s | — |
| Survey Western Lit II S | ENG010S110 | 10 | 1Y | **5.5** | core | Eng 9S or equiv | n/s | — |
| Survey Western Lit II S+ | ENG010S120 | 10 | 1Y | **5.5** | core | Eng 9S+ or equiv | n/s | — |
| Survey Western Lit II H | ENG010F130 | 10 | 1Y | **5.5** | core | Eng 9H or equiv | n/s | — |
| Survey Western Lit II H+ | ENG010F131 | 10 | 1Y | **5.5** | core | Eng 9H+ or equiv | n/s | — |
| Survey American Lit S | ENG011S110 | 11 | 1Y | **6.0** | core | Eng 10S or equiv | n/s | — |
| Survey American Lit S+ | ENG011S120 | 11 | 1Y | **6.0** | core | Eng 10S+ or equiv | n/s | — |
| Survey American Lit H | ENG011F130 | 11 | 1Y | **6.0** | core | Eng 10H or equiv | n/s | — |
| Survey British/World Lit S | ENG012S110 | 12 | 1Y | n/s¹² | core | Eng 11S or equiv | n/s | — |
| Survey British/World Lit S+ | ENG012S120 | 12 | 1Y | n/s¹² | core | Eng 11S+ or equiv | n/s | — |
| Survey British/World Lit H | ENG012F130 | 12 | 1Y | n/s¹² | core | Eng 11H or equiv | n/s | — |
| Creative Writing | ENG111E101 | 11 | 1Y | **4.5** | M3 | Honors English | n/s | chain → Adv CW |
| Advanced Creative Writing | ENG112E103 | 12 | 1Y | n/s¹² | M3 | Creative Writing G11 + work review (opt-in) | n/s | chain from CW |
| AP Lang+Comp (1Y) | ENG011F170 | 11 | 1Y | **6.0** | core-AP | Honors-plus English | n/s | — |
| AP Lang+Comp 2Y track | ENG011F171/012F171 | 11+12 | 2Y | **6.0** | core-AP | Honors English; Y1→Y2 chain; Y1→AP Lit alt | n/s | Y1→Y2 continuation |
| AP Lit+Comp | ENG012F170 | 12 | 1Y | n/s¹² | core-AP | Honors English | n/s | chain from AP Lang |
| IB English A Literature | ENG011F160/012F160 | 11-12 | 2Y | **6.0** | IB (indep sched) | Honors-plus; IB exam Y2 | n/s | — |
| IB English A Lang+Lit | ENG011F162/012F162 | 11-12 | 2Y | **6.0** | IB (indep sched) | Honors-plus; IB exam Y2 | n/s | — |
| IB English B | ENG011F161/012F161 | 11-12 | 2Y | **6.0** | IB (indep sched) | Honors English; IB exam Y2 | n/s | — |

### Math (26)
| Course | Code | Gr | Dur | Load | Mod | Pre-req / gate | Venue | Shared / no-repeat |
|---|---|---|---|---|---|---|---|---|
| Geometry S | MAT009E91GE | 9 | 1Y | **6.0** | core | Alg I (S) | n/s | → Pre-calc S |
| Geometry S+ | MAT009E92GE | 9 | 1Y | **6.0** | core | Alg I (S+) | n/s | → Pre-calc H |
| Geometry H | MAT009E93GE | 9 | 1Y | **6.0** | core | Alg I (H) | n/s | → AP Pre-calc |
| Geometry H+ | MAT009E94GE | 9 | 1Y | **6.0** | core | G9 Geo H + selection test | n/s | → AP Calculus G10 ONLY fast track |
| Pre-calculus S | MAT010E91PC | 10 | 1Y | **5.5** | core | Alg I + Geometry | n/s | → Calculus S |
| Pre-calculus H | MAT010E93PC | 10 | 1Y | **5.5** | core | Alg I + Geo S+ | n/s | → Calc H / AP AB |
| AP Pre-calculus | MAT010E50PC | 10 | 1Y | **5.5** | core | Alg I + Geo H | n/s | → AP AB/BC, IB math |
| AP Calculus (G10) | MAT010E50CL | 10 | 1Y | **6.0** | core | Alg I + Geo H+; highly prepared only; takes AP Calc BC exam | n/s | → IB MAA/MAI HL; NOT Calc S/H or AP Calc again (no-retake) |
| Calculus S | MAT011E91CL | 11 | 1Y | **6.0** | core | Pre-calc S | n/s | → AP Calc AB (G12); NOT AdvMath?? (see no-retake table) |
| Calculus H | MAT011E93CL | 11 | 1Y | **6.0** | core | Pre-calc H or AP Pre-calc | n/s | → AP Stats |
| AP Calculus AB (G11) | MAT011E51CL | 11 | 1Y | **6.0** | core-AP | AP Pre-calc or Pre-calc H + Eng S+ | n/s | → AP Stats; NOT AP Calc AB again |
| AP Calculus BC (G11) | MAT011E53CL | 11 | 1Y | **6.0** | core-AP | AP Pre-calc above-avg + Eng S+ | n/s | → Multivariable H, AP Stats; NOT AP Calc AB |
| AP Statistics (G11) | MAT011E50ST | 11 | 1Y | **6.0** | core-AP | Pre-calc H+ + Eng H + writing; social-science intent | n/s | → Stats-in-Practice H / AP Calc AB; NOT AdvMath S/H, AP Stats again |
| IB MAA HL | MAT011E73AA/012 | 11-12 | 2Y | **6.0** | IB (indep sched) | AP Calc or AP Pre-calc in G10 (Calc pref); IB exam | n/s | — |
| IB MAA SL | MAT011E71AA/012 | 11-12 | 2Y | **6.0** | IB (indep sched) | AP Calc or AP Pre-calc G10; IB exam | n/s | — |
| IB MAI HL | MAT011E73AI/012 | 11-12 | 2Y | **6.0** | IB (indep sched) | AP Calc or AP Pre-calc G10 + strong Eng; IB exam | n/s | — |
| IB MAI SL | MAT011E71AI/012 | 11-12 | 2Y | **6.0** | IB (indep sched) | AP Calc or AP Pre-calc G10 + strong Eng; IB exam | n/s | — |
| A-Level Math | MAT011E10AL/012 | 11-12 | 2Y | **6.0** | A-Level | Pre-calc (above-avg H pref); AS+A2 exams | n/s | Further Math cannot replace this |
| A-Level Further Math | MAT011E10FM/012 | 11-12 | 2Y | **6.0** | A-Level | solid Pre-calc + doing well in A-Level Math; optional, cannot replace A-Level Math | n/s | — |
| Advanced Math S | MAT012E91AM | 12 | 1Y | n/s¹² | core | Calculus S | n/s | terminal |
| Advanced Math H | MAT012E93AM | 12 | 1Y | n/s¹² | core | Calc H / AP AB / AP BC | n/s | terminal |
| Further Mathematics H | MAT012E93FM | 12 | 1Y | n/s¹² | core | Calc H or AP (G11) + aptitude | n/s | terminal |
| Multivariable Calculus H | MAT012E93MC | 12 | 1Y | n/s¹² | core | AP BC, or above-avg AP AB/Calc H + self-studied BC; instructor consult advised | n/s | terminal |
| Statistics in Practice H | MAT012E93SP | 12 | 1Y | n/s¹² | core | Calc H / AP (G11), or S-level + stats literacy; business knowledge appreciated | n/s | NOT after AP Stats G11 (no-retake) |
| AP Calculus AB (G12) | MAT012E51CL | 12 | 1Y | n/s¹² | core-AP | AP Stats G11 + passed AP exam | n/s | terminal |
| AP Statistics (G12) | MAT012E50ST | 12 | 1Y | n/s¹² | core-AP | Calc H above-avg or AP Calc + exam + Eng H + writing; social-science intent | n/s | terminal |

### Physics (16)
| Course | Code | Gr | Dur | Load | Mod | Pre-req / gate | Venue | Shared / no-repeat |
|---|---|---|---|---|---|---|---|---|
| Physics 9 H | PHY009E130 | 9 | 1Y | **3.0** | core | G8 H Physical Science; 15h practical | lab | feeds IB/AP |
| Physics 9 S+ | PHY009E120 | 9 | 1Y | **3.0** | core | G8 S Physical Science (selected); 10-12h practical | lab | — |
| Physics 9 S | PHY009E110 | 9 | 1Y | **3.0** | core | G9 S Physical Science; 6-8h practical + 1 project/sem | lab | — |
| Physics 10 H | PHY010E130 | 10 | 1Y | **3.0** | core | G9 H Physics; 15h practical | lab | feeds IB/AP |
| Physics 10 S | PHY010E110 | 10 | 1Y | **3.0** | core | G9 S Physics; 6-8h practical + project/sem | lab | — |
| Physics 11 H | PHY111E130 | 11 | 1Y | **6.0** | core/M1-sch | G10 H Physics | lab | M1 slot |
| Physics 11 S | PHY111E110 | 11 | 1Y | **6.0** | core/M1-sch | G10 S Physics; 6-10h practical + project | lab | M1 slot |
| Physics 12 H | PHY112E130 | 12 | 1Y | n/s¹² | core/M1-sch | G11 H Physics | lab | M1 slot |
| Physics 12 S | PHY112E110 | 12 | 1Y | n/s¹² | core/M1-sch | G11 S Physics; 6-10h practical + project/sem | lab | M1 slot |
| IB Physics HL | PHY111E150/112E150 | 11-12 | 2Y | **6.0** | IB (indep sched) | G10 H + IBDP req; 40h pract+10h IA+10h G4; IB exam | lab | — |
| IB Physics SL | PHY111E140/112E140 | 11-12 | 2Y | **6.0** | IB (indep sched) | G10 H + IBDP req; 20h pract+10h IA+10h G4; IB exam | lab | — |
| AP Physics 1 | PHY111E170 | 11 | 1Y | **6.0** | M1-AP | G10 H + Eng S+; 25% lab; AP exam | lab | → AP Phys 2 |
| AP Physics 2 | PHY112E170 | 12 | 1Y | **6.0** | M1-AP | AP Physics 1; 25% lab; AP exam | lab | chain from AP1 |
| AP Physics C Mech | PHY112E171 | 12 | 1Y | **6.0** | M1-AP | G11 AP Science or G11 H Physics + calculus; 25% lab; AP exam | lab | — |
| A-Level Physics AS | PHY111E180 | 11 | 1Y | **6.0** | M1-AL | G10 Physics pref; 5 required practicals (~10%); AS exam | lab | → A2 |
| A-Level Physics A2 | PHY112E180 | 12 | 1Y | **6.0** | M1-AL | AS Physics; 10 required practicals (~15%); A2 exam | lab | chain from AS |

### Chemistry (14)
| Course | Code | Gr | Dur | Load | Mod | Pre-req / gate | Venue | Shared / no-repeat |
|---|---|---|---|---|---|---|---|---|
| Chemistry 9 S | CHE009Eo10 | 9 | 1Y | **3.0** | core | G8 Physical Science; 5-6 exps | lab | N→S/S+/H streamed post-midterm (placement+midterm+behavior) |
| Chemistry 9 S+ | CHE009Eo20 | 9 | 1Y | **3.0** | core | same as S; 5-6 exps | lab | same streaming |
| Chemistry 9 H | CHE009Eo30 | 9 | 1Y | **3.0** | core | same as S; 5-6 exps | lab | same streaming |
| Chemistry 10 S | CHE010Eo10 | 10 | 1Y | **3.0** | core | G9 Chem S; 4-6 exps | lab | — |
| Chemistry 10 H | CHE010Eo30 | 10 | 1Y | **3.0** | core | G9 Chem H; 4-6 exps; pre-AP | lab | feeds AP/IB Chem |
| Chemistry 11 S | CHE011Eo10 | 11 | 1Y | **6.0** | core/M1-sch | G10 Chem S | lab | M1 slot |
| Chemistry 11 H | CHE011Eo30 | 11 | 1Y | **6.0** | core/M1-sch | G10 Chem H | lab | M1 slot |
| Chemistry 12 S | CHE012E110 | 12 | 1Y | n/s¹² | core/M1-sch | G11 Chem S | lab | M1 slot |
| Chemistry 12 H | CHE012E130 | 12 | 1Y | n/s¹² | core/M1-sch | G11 Chem H | lab | M1 slot |
| A-Level Chemistry AS | CHE011E180 | 11 | 1Y | **6.0** | M1-AL/M4-AL* | G10 Chem or equiv; AS exam | lab | *form slot M4; desc chap under Chem; → A2 |
| A-Level Chemistry A2 | CHE012E180 | 12 | 1Y | **6.0** | M1-AL/M4-AL* | AS Chemistry; A2 exam | lab | chain from AS (*same slot note) |
| IB Chemistry SL/HL | CHE011Eo40/o50/012 | 11-12 | 2Y | **6.0** | IB (indep sched) | G10 Chem H + IBDP req; IB exam | lab | SL/HL breadth-vs-depth |
| AP Chemistry | CHE011Eo70/012Eo70 | 11-12 | 1Y | **6.0** | M1-AP | G11: G10 Chem H + Eng S+; G12: G11 AP Science or G11 Chem H + Eng S+; 25% lab (≥16 hands-on, ≥6 inquiry); AP exam | lab | feeds Organic H / AP Phys C |
| Organic Chemistry H | CHE012E110 | 12 | 1Y | n/s¹² | M1-sch | G11 AP Chemistry or equiv | lab | — |

### Biology (12)
| Course | Code | Gr | Dur | Load | Mod | Pre-req / gate | Venue | Shared / no-repeat |
|---|---|---|---|---|---|---|---|---|
| Biology 9 S | BIO109Eo10 | 9 | 1Y | **4.0** | M2 (G9 pick-1) | None; lab/field/seminar | lab | — |
| Biology 9 H | BIO109Eo30 | 9 | 1Y | **4.0** | M2 (G9 pick-1) | Bio 8H + concurrent G9 Eng S+↑ | lab | — |
| Biology 10 S | BIO110Eo10 | 10 | 1Y | **3.0** | M1-combo (G10) | None | lab | — |
| Biology 10 H | BIO110Eo30 | 10 | 1Y | **3.0** | M1-combo (G10) | Bio 8H or 9H + concurrent G10 Eng S+↑ | lab | REQUIRED for IB/AP Bio |
| Elective Biology S | BIO111Eo10/112Eo10 | 11-12 | 2Y | **6.0** | M1-sch | interest in Bio; shares textbook w/ H | lab | 2Y span |
| Elective Biology H | BIO111Eo30/112Eo30 | 11-12 | 2Y | **6.0** | M1-sch | Bio 10/H + concurrent G11 Eng S+↑ | lab | 2Y span |
| AP Biology | BIO111Eo70/112Eo70 | 11-12 | 1Y | **6.0** | M1-AP | G11: Bio 10H + Eng S+ (9H rec); G12: H-Bio or AP Chem/APES in G11 + Eng S+; external AP exam mandatory | lab | — |
| AP Environmental Sci | ENV111Eo70/112Eo70 | 11-12 | 1Y | **6.0** | M4-AP (G11 form); M1-AP-GrpB (G12 form) | G11: Bio/Chem 10H + Eng H (9H Bio/Geog rec); G12: AP Bio/Chem in G11 + Eng H; AP exam | lab | M4 pick ⇒ M1≤1 + M3 blocked (G10→11 form) |
| Environmental Eng | ENV111E100/112E100 | 11-12 | 1Y | **4.5** | M3 (forms; desc header mislabels M4 — see §5) | TOEFL 90+/IELTS 6.5+/Eng S+↑ rec | n/s | repeatable across years? listed both G11+G12 cols |
| IB ESS SL | ENV111Eo40/112Eo40 | 11-12 | 2Y | **6.0** | IB (indep sched) | Bio/Chem 10H + Honors Eng; IB exam Y2 | lab | — |
| IB Biology SL/HL | BIO111Eo40/o50 + Y2 | 11-12 | 2Y | **6.0** | IB (indep sched) | Bio 10H + Honors Eng (9H rec); shared core + AHL for HL; IB exam Y2 | lab | — |
| A-Level Biology (AS→A2) | BIO111Eo80/112Eo80 | 11-12 | 2Y | **6.0** | M1-AL | Bio 10/H rec; AS exam Y1, A2 exam Y2 | lab | AS-in-M1 ⇒ no School Bio in M1 |

### Computer Science (9)
| Course | Code | Gr | Dur | Load | Mod | Pre-req / gate | Venue | Shared / no-repeat |
|---|---|---|---|---|---|---|---|---|
| Computing Essentials S | COM109E112 | 9 | 1Y | **4.0** | M2 (G9 pick-1; form: 4 cr-hrs) | English oral/written + logic pref | CS lab | feeds Comp Fund; name per render: "Computing" (desc) vs "Computer" (flowchart) |
| Programming Methodology H | COM109E130 | 9 | 1Y | **4.0** | M2 (G9 pick-1; form: 4 cr-hrs) | Math H level REQUIRED (form); G8 Math H pref | CS lab | REQUIRED Math-H gate; prereq for Honors Comp Fund 10 |
| Computer Fundamentals S | COM110E110 | 10 | 1Y | **3.0** | M2 (G10 pick-1) | none; G9 CS participation pref | CS lab | — |
| Computer Fundamentals H | COM110E130 | 10 | 1Y | **3.0** | M2 (G10 pick-1) | Programming Methodology H pref; H class selected after 1st month | CS lab | → AP CSA |
| AP Computer Science Princ | COM110E170 | 10 | 1Y | **3.0** | M2-alt (G10) | Honors Programming Methodology pref; selected after 1st month | CS lab | → AP CSA / IB CS |
| AP Computer Science A | COM111E170 | 11 | 1Y | **6.0** | M2-AP (both forms) | AP CSP or Comp Fund H (G10) requested; Java OOP | CS lab | chain from CSP/H-Fund |
| IB Computer Science SL | COM111E140/112E140 | 11-12 | 2Y | **6.0** | IB (indep sched) | AP CSP or Comp Fund H pref; IB exam | CS lab | SL: no HL-only Topic 84 |
| IB Computer Science HL | COM111E150/112E150 | 11-12 | 2Y | **6.0** | IB (indep sched) | same as SL; IB exam | CS lab | +abstract data types, collab-sci project |
| Computer Skills | COM111E100/112E100 | 11/12 | 1Y | **4.5** | M3 | none (designed for little/no CS background; Python+AI literacy) | CS lab | offered G11 AND G12 |

### Social Sciences / Econ-Business / Psychology (20)
| Course | Code | Gr | Dur | Load | Mod | Pre-req / gate | Venue | Shared / no-repeat |
|---|---|---|---|---|---|---|---|---|
| Economics&Business optional | (optional code) | 9-12 | Sem | **1.5-2 periods** | optional | None; transcript-listed, NOT in GPA | n/s | Sem; feeds G10 Econ track |
| Life Skills | (optional code) | 9-12 | Sem | n/s (1hr HW) | optional | None; transcript-listed, NOT in GPA | varies (driving sim/flower/tea etc) | Sem |
| Economics and Business S | ECO110E110 | 10 | 1Y | **4 teaching periods** | M2 (G10 pick-1) | None; level set after 1st month (Eng+test) | n/s | G9 must pick?? see gate E-g1: G10-Micro selection needs G10 Econ&Business |
| Economics and Business H | ECO110E130 | 10 | 1Y | **4 teaching periods** | M2 (G10 pick-1) | None; move-up tests after midterm/final; Eng H/TOEFL100+/IELTS7.5+ for H | n/s | feeds AP Micro / IB Econ / IB BusMgmt |
| AP Microeconomics | ECO110E170/111E170 | 10/11 | 1Y | **4.5 periods** | M2-AP/M4-AP* | G10: must have chosen Econ&Business G10, selected after 1st month; *M4 slot in G10→11 form; M2 slot in G11→12 form (conflict — §5) | n/s | → AP Macro (rec); M4-pick ⇒ no AP in M3 |
| AP Macroeconomics | ECO111E171/112E170 | 11/12 | 1Y | **4.5 periods** | M2-AP/M4-AP* | AP Micro G10 rec; *M2 and M4 both listed across forms | n/s | chain from Micro |
| AP Business w/ Personal Fin | (no code given) | 12 | 1Y | **3 periods** | M2 (G12) | None; digital Bluebook exam (MCQ+FRQ: Business Canvas + Financial Advisor projects) | n/s | terminal |
| IB Economics SL/HL | ECO111E160/112E160 | 11-12 | 2Y | **4.5 periods** | IB (indep sched) | Econ H G10 or AP Micro rec; same syllabus; SL+HL SAME classroom (mid/final same papers; HL extra commentary + split papers Sem2-Y2); IB exam | n/s | cross-level shared room |
| IB Business Mgmt SL | BUS111E140/112E140 | 11-12 | 2Y | **4.5 periods** | IB (indep sched) | AP Micro or Econ HL rec; SL only; IB exam | n/s | — |
| AQA A-Level Economics | ECO111E180/112E180 | 11-12 | 2Y | **4.5 periods** | M2-AL | G10 Econ H or AP Micro rec; AS=P1/2 exam Y1, A2=P3/4 exam Y2 | n/s | M2 "choose one only" w/ AS Further Math |
| Business Management | ECO111E130/112E130 | 11/12 | 1Y | **3 periods** | M3 | None | n/s | G11+G12 IDENTICAL contents = shared slot; mock interview/debate/negotiation in class |
| Accounting | ACC112E130 | 12 | 1Y | **4.5 periods** | M2 (G12) | English honors REQUIRED; logic/analytical helpful; US GAAP full-cycle | n/s | G12 only |
| Introduction to Law | LAW111E130/112E130 | 11/12 | 1Y | **4.5** | M3 | None; mock trials + legal-writing thru yr | n/s (mock-trial room) | offered both yrs |
| Introduction to Sociology | SOC111E130/112E130 | 11/12 | 1Y | **4.5** | M3 (G12 only per render; §5) | None; grading 30/30/40 (proj/mid/final) | n/s | G11-M3 listing conflict (§5) |
| School Psychology | PSY111E100/112E100 | 11/12 | 1Y | **4.5** | M3 | NONE if AP Psych taken in G11 (bar); G11+G12 IDENTICAL contents = shared slot | n/s | AP-Psych-taker bar |
| AQA A-Level Psychology | PSY111E180/112E180 | 11-12 | 2Y | **6.0** | M4-AL | None; unit exams Jan/May-Jun, resits allowed (best counts) | n/s | M4 "choose one only" w/ AS Chemistry |
| AP Psychology | PSY111E170/112E170 | 11/12 | 1Y | **4.5 periods** | M2-AP | Eng H (G10) pref | n/s | blocks school Psych in M3 (both yrs) |
| IB Psychology SL | PSY111E140/112E140 | 11-12 | 2Y | **4.5 periods** | IB (indep sched) | English H+; IB exam | n/s | — |
| IB Psychology HL | PSY111E140/112E140 | 11-12 | 2Y | **4.5 periods** | IB (indep sched) | English H+; deeper stats/IA; IB exam | n/s | — |
| Optional Psychology | PSY20HE001 | 9-12 | Sem | **1.5 periods** | optional | None (Eng comprehension needed); HW bi-weekly | n/s | Sem |

### Geography (6)
| Course | Code | Gr | Dur | Load | Mod | Pre-req / gate | Venue | Shared / no-repeat |
|---|---|---|---|---|---|---|---|---|
| Physical Geography S | GEO109E110 | 9 | 1Y | **4.0** | M2 (G9 pick-1; form: 4 cr-hrs) | None; facts-oriented | n/s | — |
| Physical Geography H | GEO109E130 | 9 | 1Y | **4.0** | M2 (G9 pick-1; form: 4 cr-hrs) | Geog 8S+/8H + Eng S+; GIS/computer-skill demand (junior advice) | comp lab (GIS) | — |
| Human Geography 1 S | GEO110E110 | 10 | 1Y | **3.0** | M2 (G10 pick-1) | None | n/s | — |
| Human Geography 1 H | GEO110E130 | 10 | 1Y | **3.0** | M2 (G10 pick-1) | Geog 8S+/8H/9H + Eng S+ | n/s | feeds AP Human Geo |
| Human Geography 2 ("Geography" on G11→12 form) | GEO111E110 | 11 | 1Y | **4.5** | M2 | None | n/s | form-label mismatch (§5) |
| AP Human Geography | GEO111E170 | 11 | 1Y | **6.0** | M2-AP | Geog 10H + Eng 10S+; ≥6hrs HW (heaviest stated) | n/s | G11 only per forms |

### History / Philosophy (16)
| Course | Code | Gr | Dur | Load | Mod | Pre-req / gate | Venue | Shared / no-repeat |
|---|---|---|---|---|---|---|---|---|
| World Hist to 1500 S | HIS009E110 | 9 | 1Y | **4.0** | core | None | n/s | — |
| World Hist to 1500 S+ | HIS009E120 | 9 | 1Y | **4.0** | core | 8S+ Hist + Eng S+ | n/s | — |
| World Hist to 1500 H | HIS009E130 | 9 | 1Y | **4.0** | core | 8H Hist + Eng H | n/s | — |
| World Hist since 1500 S | HIS010E110 | 10 | 1Y | **4.0** | core | 9S | n/s | — |
| World Hist since 1500 S+ | HIS010E120 | 10 | 1Y | **4.0** | core | 9S+ | n/s | — |
| World Hist since 1500 H | HIS010E130 | 10 | 1Y | **4.0** | core | 9H | n/s | feeds AP World/US |
| AP World History | HIS110E170/111E170 | 10/11 | 1Y | **4.0** (G10) / **6.0** (G11) | M2-AP/core-alt | Hist H + Eng H+; exam in May (~3 semesters coverage) | n/s | — |
| US Overview S | HIS111E110 | 11 | 1Y | **4.5** | M2 | None | n/s | — |
| US Overview H | HIS111E130 | 11 | 1Y | **4.5** | M2 | English H+; feeds AP US Hist | n/s | — |
| Traditional China S | HIS111E111 | 11 | 1Y | **4.5** | M2 | Chinese Native; taught in Chinese | n/s | native-gate |
| Traditional China H | HIS111E131 | 11 | 1Y | **4.5** | M2 | Chinese Native H; taught in Chinese; +essay+project/sem | n/s | native-gate |
| Western Civilization 1 S | HIS111E112 | 11 | 1Y | **4.5** | M2 | None | n/s | — |
| Western Civilization 1 H | HIS111E132 | 11 | 1Y | **4.5** | M2 | English H+ | n/s | high-Eng gate (junior advice Q5) |
| Western Civilization 2 S | HIS112E110 | 12 | 1Y | n/s¹² | M2 (G12) | None | n/s | cannot repeat G11 course |
| Western Civilization 2 H | HIS112E130 | 12 | 1Y | n/s¹² | M2 (G12) | English H+ | n/s | cannot repeat G11 course |
| Amer Govt+Politics S | HIS112E111 | 12 | 1Y | n/s¹² | M2 (G12) | None; pairs w/ US Hist G12 | n/s | G12 only; high-Eng demand (Q5) |
| Amer Govt+Politics H | HIS112E131 | 12 | 1Y | n/s¹² | M2 (G12) | English H+ | n/s | G12 only |
| AP US History | HIS111E171/112E171 | 11/12 | 1Y | **6.0*** | M2-AP | 10H Hist + Eng H+, or G11 US-Overview H + Eng H+ | n/s | — |
| AP Art History | HIS111E172/112E172 | 11/12 | 1Y | **6.0*** | M2-AP | from G10: Eng H+ + Hist 10 S+↑; from G11: AP Eng + AP socsci/humanities; 250 works/10 units | n/s | heaviest prereq chain in M2 |
| IB World History SL/HL | HIS111E160/112E160 | 11-12 | 2Y | **6.0** | IB (indep sched) | 10H Hist or 10 AP World + Eng H; P1+P2 (+P3 HL: Europe/Africa/Americas); IA drafts; IB exam | n/s | — |
| School Philosophy | PHI111E100/112E100 | 11/12 | 1Y | **4.5** | M3 | advanced written/oral English | n/s | ONLY course repeatable G11→G12 |
| IB Philosophy SL | PHI111E140/112E140 | 11-12 | 2Y | **6.0** | IB (indep sched) | H+ English; core theme "being human" + Descartes Meditations + IA on non-phil stimulus; IB exam | n/s | — |

### Fine Arts (21)
| Course | Code | Gr | Dur | Load | Mod | Pre-req / gate | Venue | Shared / no-repeat |
|---|---|---|---|---|---|---|---|---|
| Arts (G9) | ART109E100 | 9 | 1Y | **2.0** | M3 (G9 pick-1; form: 2 cr-hrs, letters) | Fine Arts Skills | art studio | woodcut/watercolor/sketch/Gongbi/freehand/oil/computer |
| Visual Arts Standard | ART110E110 | 10 | 1Y | **3.0** | M2 (G10 pick-1) | basic drawing | art studio | — |
| Visual Arts Honors | ART110E130 | 10 | 1Y | **3.0** | M2 (G10 pick-1) | Fine Arts Skills | art studio | feeds IB VA + AP Drawing/3-D; portfolio rsrch |
| IB Visual Arts SL Y1+Y2 | ART111E140/112E140 | 11+12 | 2Y | **6.0** | IB (indep sched) | G10 VA H or AP Drawing; exhibit + online portfolio; 8-12 studio + 15-20 IWB pgs; IB exam | art studio | Y1→Y2 chain |
| IB Visual Arts HL Y1+Y2 | ART111E150/112E150 | 11+12 | 2Y | **6.0** | IB (indep sched) | same; 12-18 studio + 25-30 IWB pgs; IB exam | art studio | Y1→Y2 chain |
| AP Drawing | ART110E170/112E170 | 10/11 | 1Y | **6.0** | M4-AP (G10→11 form) / M2-AP (G11→12 form G11 col) — CONFLICT §5 | G10: 1-2 works month-1 must pass; G11: G10 VA + portfolio review, HL pref; AP portfolio review | art studio | breadth+quality+concentration portfolio |
| AP 3-D Art and Design | ART111E172 | 11 | 1Y | **6.0** | M4-AP (G10→11) / M2-AP (G11→12 G11 col) — CONFLICT §5 | G10 VA + portfolio review | art studio | sculpture/render/metal/ceramics portfolio |
| Drawing Y1 | ART111E100 | 11 | 1Y | **4.5** | M4 | basic drawing | art studio | → Drawing Y2 chain |
| Drawing Y2 | ART112E100 | 12 | 1Y | n/s¹² | M4-cont | Drawing Y1 | art studio | chain from Y1 |
| Arts 1 | (M4) | 11 | 1Y | **4.5** | M4 | (G10 VA track) | art studio | → Arts 2 chain (flow chart; no G12 checkbox — §5) |
| Arts 2 | (M4-cont) | 12 | 1Y | n/s¹² | M4-cont | Arts 1 (continuation rule) | art studio | chain from Arts 1 |
| Woodcut Printing | ART206No15 | 9-10 | 1Y | n/s | elective | basic drawing | art studio | — |
| Computer Design | ART209No19 | 9-10 | 1Y | n/s | elective | basic drawing | comp/art lab | — |
| Intermediate Watercolor | ART2JHN001 | 9-10 | 1Y | n/s | elective | basic drawing | art studio | → Advanced Watercolor |
| Fashion Design | ART2JHN002 | 9-10 | 1Y | n/s | elective | basic drawing | art studio | — |
| Intermediate Sketching | ART2JHN003 | 9-10 | 1Y | n/s | elective | basic drawing | art studio | → Advanced Sketching |
| Oil Painting Foundations | ART209Noo4 | 9-10 | 1Y | n/s | elective | basic drawing | art studio | → Intermediate Oil |
| Chinese Freehand Painting | ART306No11 | 9-10 | 1Y | n/s | elective | basic drawing | art studio | flower/bird/landscape |
| Illustration and Design | ART2JHN004 | 9-10 | 1Y | n/s | elective | basic drawing | art studio | → adv Illustration (11-12) |
| Advanced Watercolor | ART2SHN001 | 11-12 | 1Y | n/s | elective | basic drawing | art studio | adv chain |
| Illustration and Design adv | ART2SHN002 | 11-12 | 1Y | n/s | elective | basic drawing | art studio | adv chain |
| Advanced Sketching | ART2SHN003 | 11-12 | 1Y | n/s | elective | basic drawing (plaster busts/figure) | art studio | adv chain |
| Intermediate Oil Painting | ART211Noo5 | 11-12 | 1Y | n/s | elective | basic drawing | art studio | adv chain |

### Music & Drama + World Languages (26)
| Course | Code | Gr | Dur | Load | Mod | Pre-req / gate | Venue | Shared / no-repeat |
|---|---|---|---|---|---|---|---|---|
| Music+Perf Arts Culture+Admin | MUS109E100 | 9 | 1Y | n/s | G9 music | None; 2 tracks (pop creation / art mgmt); school-activity practicum | regular classroom | — |
| Music (G9 M3 choice) | (M3) | 9 | 1Y | **2.0** | M3 (G9 pick-1; form: 2 cr-hrs, letters) | None | music room | — |
| Music Appreciation HL | MUS110E130 | 10 | 1Y | **3.0** | M2 (G10 pick-1) | None (no instrument/theory needed); grading 30/40/30 | classroom+rehearsal+studio | diagnostic month-1 ⇒ AP Music Theory G10 |
| AP Music Theory (G10 path) | MUS110E170 | 10 | 1Y | **3.0~** | M2-adv | Honors MusicAppr + pass diagnostic (intervals/dictation/sight-sing C,G,F,A,E,Dm) + Eng S+↑ | music room | ~ = G10 band inferred; not in .gpa list |
| AP Music Theory (G11/12) | MUS112E170 | 11/12 | 1Y | **6.0*** | M3-AP | good standing + pitch accuracy; Kostka/Payne + 60min/wk aural self-study | music room | sole AP in M3 |
| Western Theatre | MUS110E131 | 10 | 1Y | **3.0** | M2 (G10 pick-1) | None; IB Theatre pre-college prep rec | stage/drama | → IB Theatre rec |
| A Cappella & Ensemble (G11) | MUS111E100 | 11 | 1Y | **4.5** | M4 | sing in tune; INTERVIEW req; harder repertoire + rearranging | music room/stage | chain from 9/10 A Cappella |
| Opera+German-Austrian Art Song | MUS111E102/112E103 | 11 | 1Y | **4.5** | M4 | None (bel canto; Italian/German diction) | music room/stage | form label "Art Song Singing" |
| Applied Acting Technique | MUS111E101 | 11 | 1Y | **4.5** | M4 | None; Stanislavski/Brecht/Artaud/Lecoq/Berkoff; monologue Y1 + devised play Y2 | stage/drama (venue designation) | — |
| Digital Music Design | MUS112E104 | 12 | 1Y | n/s¹² | M4 (G12) | None; grading 30/40/30 (bimonthly 70 + projects 30); 2000-word project report | music tech studio | G12 only |
| Dramaturgy+Dramatic Criticism | MUS112E102 | 12 | 1Y | n/s¹² | M4 (G12) | None; 5-pg essay/sem + live-review essay | stage/drama | form label "Drama" |
| IB Music SL/HL | MUS111E140/150 + Y2 | 11-12 | 2Y | **6.0** | IB (indep sched) | G10 MusicAppr or application+interview (research/create/perform tri-role); HL +15min contemporary-maker video; IB exam | music rooms/studio | — |
| IB Theatre | MUS111E141/112E141 | 11-12 | 2Y | **6.0** | IB (indep sched) | G10 Western Theatre strongly rec + Eng H+ rec; play-texts/world-traditions/devised/HL-history; grading 30/40/30 | stage/drama (designation critical) | — |
| Dance optional | MUS20HE001 | — | Sem | n/s (cat: Sem) | optional | None (pop+jazz; choreography w/ instructor) | dance studio | Sem |
| Music Design+Production opt | MUS20HE002 | — | Sem | n/s (cat: Sem) | optional | music background (have played); take own piece home | music tech | Sem |
| A Cappella & Ensemble (9/10) | MUS20HE003 | 9-10 | Sem | n/s (cat: Sem) | optional | sing in tune | music room | → G11 A Cappella |
| Wind Ensemble | MUS20HE004 | 7-12 | n/s | n/s | optional | INTERVIEW req; chamber sub-groups; Art Festival comps | music room | cross-grade (7-12) |
| Classical+Improv Piano | MUS20HE005 | — | Sem | n/s (cat: Sem) | optional | piano skills (begin/interm + improv/accompaniment tracks) | piano room | Sem |
| Guitar optional | MUS20HE006 | — | Sem | n/s (cat: Sem) | optional | None (classical+folk; solo + sing-and-play) | music room | Sem |
| Drama+Theater Studies opt | MUS20HE008 | — | Sem | n/s (cat: Sem) | optional | None (acting + history/lit/tech; solo/duet/ensemble) | stage/drama | Sem |
| Chamber Music String Quartet | MUS20HE009 | — | 1Y | n/s | optional | instrument background; per-instrument lessons + ensemble | music room | perform/compete in+out school |
| World Language French | LAN111E130/112E130 | 11-12 | 2Y | **3.0** | M3/M4 | None; 4 sub-levels (prelim+L1-3); TEF target; Taxi! 1-3 | language room | Y1+Y2 chain |
| World Language Japanese | LAN111E132/112E132 | 11-12 | 2Y | **3.0** | M3/M4 | None; L1 G11/L2 G12; JLPT target; Adventures+Dekiru | language room | Y1+Y2 chain |
| World Language Spanish | LAN111E132/112E132 | 11-12 | 2Y | **3.0** | M3/M4 | None; 3 levels → DELE B2; Sueña 1-2 | language room | Y1+Y2 chain |
| Global Mindset thru Cross-Cult | (gen-ed) | 9-10 | weekly | 1 period (cat; no .gpa) | gen-ed | None; culture-not-language (Fr/Ger/Jpn/Lat/Span lens) | regular classroom | 1 period/wk |
| IB French ab initio Y1+Y2 | LAN111E161/112E161 | 11-12 | 2Y | **6.0** | IB (indep sched) | no/very limited French; 5 IB themes; IB exam | language room | — |
| IB Spanish ab initio Y1+Y2 | LAN111E160/112E160 | 11-12 | 2Y | **6.0** | IB (indep sched) | no/very limited Spanish; IB exam | language room | — |

### Physical Education (13, all Semester, G9-12)
| Course | Code | Gr | Dur | Load | Mod | Pre-req / gate | Venue | Shared / no-repeat |
|---|---|---|---|---|---|---|---|---|
| Basketball | GYM1JHN001/SHN001 | 9-12 | Sem | n/s | PE | None | gym | Sem; JHN=G9-10, SHN=G11-12 codes |
| Soccer | GYM1JHN002/SHN002 | 9-12 | Sem | n/s | PE | None | field | Sem |
| Volleyball | GYM1JHN003/SHN003 | 9-12 | Sem | n/s | PE | None | gym | Sem |
| Tennis | GYM1JHN004/SHN004 | 9-12 | Sem | n/s | PE | None | courts | Sem |
| Baseball | GYM1JHN005/SHN005 | 9-12 | Sem | n/s | PE | None (upper grades: pitch/catch/bunt/steal) | field | Sem |
| Ping Pong | GYM1JHN006/SHN006 | 9-12 | Sem | n/s | PE | None | gym | Sem |
| Badminton | GYM1JHN007/SHN007 | 9-12 | Sem | n/s | PE | None | gym | Sem |
| Track and Field | GYM1JHN008/SHN008 | 9-12 | Sem | n/s | PE | None (run/jump/throw + comps) | field/track | Sem |
| Aerobics | GYM1JHN009/SHN009 | 9-12 | Sem | n/s | PE | None | gym/studio | Sem |
| Swimming | GYM1JHN010/SHN010 | 9-12 | Sem | n/s | PE | None (self-survival emphasis) | POOL (venue lock) | Sem |
| Taekwondo | GYM1JHN011/SHN011 | 9-12 | Sem | n/s | PE | None; self-control/discipline component | dojo | Sem |
| Karate | GYM1JHN012/SHN012 | 9-12 | Sem | n/s | PE | None | dojo | Sem |
| Kendo | GYM1JHN013/SHN013 | 9-12 | Sem | n/s | PE | None (shinai basics) | dojo | Sem |

### Academy / PBL / R-TEW (4)
| Course | Code | Gr | Dur | Load | Mod | Pre-req / gate | Venue | Shared / no-repeat |
|---|---|---|---|---|---|---|---|---|
| Academy | — | 9-12 | ongoing | n/s (cat: once a week; part of class schedule) | co-curric | academically ready + discuss/share/cooperate; teacher-supervised, student-initiative | varies | teamed by grade; links CAN cross grades |
| Project-based Learning (S/Challenge) | — | 10 | n/s | n/s | PBL | Standard (guided) vs Challenge (own question); lab+Chinese-tradition+writing; showcase weeks ~16-18 (paper/comps/poster/fair) | lab/vary | grading LETTERS A/B/C/D biannual |
| R-TEW G9 | — | 9 | 1Y | n/s (cat: weekly seminar) | co-curric | weekly topic; Blackboard posts (serious+light+multimedia) + monthly creative piece → anthology; Living Wechat Group | seminar room | G9=self-identity focus |
| R-TEW G10 | — | 10 | 1Y | n/s (cat: weekly seminar) | co-curric | same mechanism | seminar room | G10=self-vs-community focus |

## (1) Class-size caps / floors
- Floor: course runs ONLY if >5 students apply (catalog p.6; literal ">5"). NO maximum class-size caps stated anywhere (full-text grep for cap/max-size/size-limit: nil).
- De-facto gates (function as caps): AP Micro G10 post-month-1 selection; A Cappella/Wind Ensemble interview/audition; AP Music Theory G10 diagnostic; level streaming (G9 Chem N→S/S+/H; G10 CompFund H / AP CSP after 1st month; G10 Econ S/H after 1st month); forced move-down (fail ≥2 subjects/semester; 2 teacher reports for IB/AP; auto-withdrawal per Guidelines); admin approval for G10 M2; director + IB/AP-coordinator sign-off for level changes; same-level class change FORBIDDEN.

## (2) Assessment / grading scales
- .gpa scoreMaps (AUTHORITATIVE for GPA calc): default: 0 F 0.0 / 60 D/C 2.6 / 68 C+ 3.0 / 73 B- 3.3 / 78 B 3.6 / 83 B+ 3.9 / 88 A- 4.2 / 93 A/A+ 4.5. AP: 1→0.0/2→1.0/3→2.5/4→3.5/5→4.5. ASA2: U→0.0/E→1.0/D→2.5/C→3.0/B→3.5/A→4.0/A*→4.5. IB: 1→0.0/2→2.0/3→2.5/4→3.0/5→3.5/6→4.0/7→4.5. Level offsets: school S +0.5/H +0.2 (G9-10; G11 M1 S +0.5/H +0.25); H+ +0.0-0.1; AP/AS/IB levels +0.0 with tags.
- Catalog prose: G9 M3 = Letters Grade System; PBL = letters A/B/C/D biannual; optionals (Econ&Business, Life Skills) = transcript-listed but NOT in GPA; Intro Sociology 30/30/40 (proj/mid/final); MusicAppr 30/40/30; DigitalMusicDesign 30/40/30 (bimonthly 70+proj 30); IB Theatre 30/40/30 (monthly 70+essays 30); IB Music 30/40/30 (listening+portfolio+recital). Everything else: n/s (default presumed marks-based; .gpa default map applies).

## (3) Fixed-time blocks constraining the grid
- No clock times / period lengths / periods-per-day stated anywhere (neither catalog nor .gpa; units differ: credit-hrs vs teaching-periods vs periods).
- Blocks occupying grid space (times n/s): Homeroom System; Assembly; Camping; Senior Project; Academy (weekly, IN class schedule, grade-teamed); R-TEW (weekly seminar); PBL (course + showcase weeks 16-18); CAS (core; IB CAS); PE (all optionals Semester); Global Citizen Program; clubs/ASB (extension of Academy); Music/Drama/Festival performances+comps; lab practicals (fixed venue-hours: Phys 6-40h/yr by level; Chem 4-6 exps; AP sciences 25% instructional time; IB Phys SL 20/HL 40 + IA 10 + G4 10; A-Level Phys AS ~10%/A2 ~15%).
- IBD independent schedule: IBDP↔school/AP transfers NOT supported (schedule confliction) ⇒ IB grid is a separate partition.

## (4) Exclusion / gating chains (complete list)
E1. G9 M2 pick exactly 1 (Bio/Computing/Prog/PhyGeo). E2. G9 M3 pick exactly 1 (Music/Arts). E3. G9 ProgMethodology-H REQUIRES Math-H. E4. G9 Chem single N → streamed S/S+/H post-midterm (placement+midterm+behavior; holistic). E5. G8 Phys H→G9 H; selected G8 S→G9 S+ (scores+behavior). E6. G10 M1 = exactly one combo (Phy+Chem/Chem+Bio/Phy+Bio). E7. G10 M2 pick 1 (+admin approval by academic status). E8. G10 AP Micro: must have chosen G10 Econ&Business + post-month-1 selection. E9. G10 AP CSP / CompFund-H / Econ-level: selected/set after 1st month. E10. G11 M1 ≤2; 2-in-M1 ⇒ M3=M4=0 (.gpa dynamicLimits trigger moduleIdx2 → target 4,5 = 0; module indices 0-based: core0,lang1,M1 2,M2 3,M3 4,M4 5). E11. G11 M2 = 1. E12. G11 M3 ≤1 (or No Choice); M4 ≤1 (or No Choice). E13. AP Micro/Macro in M2 ONLY IF (2 AP in M1) OR (1 AP in M1 AND AP ES/Drawing/3-D in M4) — form rule; .gpa econ_ap_rule encodes it (M2-Econ + exactly-1-AP-in-M1 ⇒ requires M4-Drawing/3D). E14. M4 AP-ES ⇒ M1≤1 AND M3=0 (.gpa ap_es_rule: M2-limit→1, M4-limit→0). E15. M4 AP-Econ/Drawing/3-D ⇒ no AP in M3. E16. AS-in-M1 ⇒ no School Biology in M1; AS-Phys vs AS-Bio choose ONE only. E17. AS-in-M4 ⇒ M1≤1 + M3=0; AS-Chem vs AS-Psych choose ONE only. E18. M2 AS-Econ vs AS-FurtherMath choose ONE only. E19. AP Psych (M2, either yr) ⇒ school Psychology (M3) barred both yrs. E20. School Psych takers (G11 AP Psych) barred from G12 school Psych. E21. G11→G12 M2/M4: cannot repeat same course (M3: except No-Choice + Philosophy). E22. G11 M3-only ⇒ G12 M3-or-M4; G11 A-Cappella-only ⇒ G12 M3-or-M4; both M3+M4 ⇒ may drop one school course in G12; M4 G11 courses continue into G12. E23. ExclusionIds: M2-AP-Micro vs M4-AP-Micro (same subject twice); M2-AP-Macro vs M4-AP-Macro. E24. Math no-retake table (render-verified 72.webp): G9 H+→AP Calc G10; G10 AP Calc→IB MAA/MAI HL (NOT Calc S/H, AP Calc); G11 AP Stats→StatsPract-H/AP Calc AB (NOT AdvMath S/H, AP Stats); G11 AP BC→Multivar-H/AP Stats (NOT AP AB); G11 AP AB-or-Calc H→AP Stats (NOT AP AB); G11 Calc S→(no recommendation; NOT AP AB). E25. Bio 10H REQUIRED for IB/AP Biology; AP Bio G12 requires H-Bio or AP Chem/APES in G11. E26. CS chain: ProgMethod-H → CompFund-H → AP CSA; AP CSP → AP CSA/IB CS; IB CS G11 → IB CS G12. E27. Music chain: MusicAppr-H + diagnostic → AP Music Theory G10; 9/10 A Cappella → G11 A Cappella (interview). E28. Art chain: G10 VA + portfolio → AP Drawing/3-D; Drawing Y1→Y2; Arts 1→Arts 2. E29. Eng chains: AP Lang 2Y Y1→Y2; AP Lang→AP Lit; 9H Bio/Geog recommended for APES; 10H Hist + Eng H for AP World/US/ArtHist. E30. Level-change gates: move-up needs written application + test + 3-way consult + director (+IB/AP coord); move-down forced on ≥2 fails or 2 teacher reports; A-Level auto-withdrawal; same-level switch forbidden. E31. Floor >5 to run; IBD↔school/AP transfer blocked. E32. .gpa exclusionTags [["AP","nonAP"]] + requirements triggerTag AP (with joke message — treat as placeholder, confirm with repo owner).

## (5) Corrections to catalog_extract.md
R1. G11 M3 school list: extract added "Intro to Sociology" — render 14.webp G11 col has NO Sociology (G12 only). REMOVE. R2. World Language in M3: present in BOTH G11 and G12 cols (not "G12 adds"). FIX. R3. G11→G12 M4 AP: G11 = Macro/ES/Micro; G12 = Macro ONLY (extract implied ES+Micro+DRAW+3D in G12 M4 — WRONG). R4. G12 M2 AP = Psych/MusicTheory/USHist/Macro/ArtHist ONLY (extract listed Drawing/3-D/HumanGeo/Micro/CSA/WorldHist — WRONG; also extract duplicated "AP Macroeconomics"). R5. G11 M2 school per G11→12 form = "Geography" (description chap = Human Geography 2 GEO111E110) — label mismatch; G11 M2 AP per same form INCLUDES AP Drawing + AP 3-D (CONFLICTS with G10→11 form M4 placement — inter-form inconsistency, see R9). R6. Environmental Engineering: description header says "(Module 4)" but ALL forms place it in M3 ⇒ M3 governs. R7. G12 M4 "Drama" = Dramaturgy & Dramatic Criticism; "Art Song Singing" = Opera&German-Austrian Art Song; "Arts 2" checkbox MISSING in G12 M4 despite continuation rule+flowchart — flag as form gap. R8. Music Appreciation "HL" is its literal name (MUS110E130), not a level variant. R9. INTER-FORM CONFLICT: AP Drawing/3-D/AP Micro sit in M4 (G10→11 form) but in M2-G11-col (G11→12 form); AP Art History missing from G11→12 G11-col M2; "AP Music Theory" appears in G11→12 G12-col M2 (absent from G10→11 M2). .gpa sides with G10→11 form (Drawing/3D in M4; ArtHist in M2). R10. Math table: G11 Calculus S row has EMPTY recommendation cell (render-verified) + print typo "AP Staticitics" (=AP Statistics). R11. .gpa G11 M3 INCLUDES Intro to Sociology (sides with catalog text, contradicts render 14.webp G11 col) — .gpa-vs-render conflict to confirm. R12. Extract C2 "AP Drawing G10 or 11 feeds M4 constraint" — correct per G10→11 form only; G11→12 form moves it (see R9). R13. Extract §b G10→11 AP M2 school list confirmed correct (US Overview/HumanGeo2/ChineseHist/WestCiv1). R14. Chemistry G9 N-streaming + English H+ tier + ">5" floor confirmed literal. R15. pypdf garbles ("Chem istry","1B","Psycho logy", split codes) confirmed cosmetic only; no course missed — full-text course inventory reconciles 1:1 with flowcharts except R7/R9 gaps.

## (6) Load authority: Courses.gpa (Spring 2026, v3.4) — overrides catalog prose
Bold Load values = .gpa weight. `*` = .gpa covers G9/10/11AP/IB/A-Level bands; G12-only rows have NO .gpa band ⇒ n/s¹². `~` = band-inferred (course absent from .gpa list). Plain values = catalog prose retained where .gpa silent (optionals/PE/co-curric).
Weight map applied: G9 core Eng/Math 6.0, Chi/Phy/Chem 3.0, Hist 4.0, M2 4.0, M3 2.0. G10 core Eng/Math 5.5, Chi 3.0, Hist 4.0, M1 3.0 ea, M2 3.0 (Econ 4.0); G10-Chi-AP(L7) 3.0, WHAP(L) 4.0, Math-AP levels 5.5. G11AP core Eng/Math 6.0, Lang 3.0, M1 6.0 ea, M2-M4 school 4.5 / AP 6.0. A-Level: core Eng/Math 6.0, Lang 3.0, M1 6.0, M2 school 4.5 / AS 6.0, M3 4.5, M4 school 4.5 / AS 6.0. IB: every IB subject 6.0, ToK 3.0 (no ToK course row — core-only). Templates: school_SH 4.5, AP_only 6.0, grade10_SH3 3.0, AS_only 6.0, IB_subject 6.0.
DISCREPANCIES (.gpa wins; catalog prose wrong/stale): D1. AP Micro/Macro catalog "4.5 periods" ⇒ .gpa 6.0. D2. AP Psych "4.5" ⇒ 6.0. D3. Business Mgmt "3 periods" ⇒ 4.5. D4. IB Econ/BusMgmt/Psych "4.5" ⇒ 6.0. D5. AQA Econ "4.5" ⇒ 6.0. D6. World Languages "3 teaching periods" = 3.0 ✓ MATCH. D7. AP Business w/ PF "3 periods" — no G12 band ⇒ n/s¹² (catalog value preserved here only). D8. Accounting "4.5" — no G12 band ⇒ n/s¹² (catalog value preserved here only). D9. G10 Econ&Business "4 teaching periods" = 4.0 ✓ MATCH. D10. G9 M2 "4 credit hrs" = 4.0 ✓; G9 M3 "2 credit hrs" = 2.0 ✓ MATCH. D11. Optionals/PE/Academy/PBL/R-TEW/GlobalMindset: no .gpa entries ⇒ catalog values kept (1.5-2, 1.5, 1 period, weekly, Sem). D12. `Courses.catalog` in same folder is known-flaky — NOT used.
Machine rules (.gpa `rules`, G11 AP track): exclusionIds micro (M2↔M4) + macro (M2↔M4); dynamicLimits 2-in-M1 ⇒ M3/M4 limit 0; econ_ap_rule (M2-Econ + exactly-1-AP-in-M1 ⇒ needs M4-Drawing/3D); ap_es_rule (M4-AP-ES ⇒ M1 limit 1 + M3 limit 0). NOTE: .gpa module indices are 0-based over [core,lang,M1,M2,M3,M4].
Counts: 230 rows (16 Chi + 22 Eng + 26 Math + 16 Phy + 14 Chem + 12 Bio + 9 CS + 20 Soc + 6 Geo + 22 Hist/Phil + 23 Arts + 26 Mus/Drama/WL + 13 PE + 4 Acad/PBL/RTEW + 1 Music-G9 = 230). Loads: .gpa-bold 165 rows; n/s¹² (G12-only) 25; catalog-retained-or-n/s (optionals/PE/co-curric/electives) 40. No clock times anywhere; no max caps anywhere.



---
## Appendix: diagram-page transcriptions (vision; low scheduling relevance)
Moved verbatim from the retired catalog_extract.md so this file is the single extract.

## (a) Diagram-page transcriptions (vision)

### A1. PDF p.5 = printed p.3 = `3.webp` — High School Co-curriculum Model (tree diagram)
Four trunk branches (the "four dimensions" from Foreword p.2):
- **Virtues & Values** (left canopy): leaves = Friendship, Confidence, Integrity, Respect, Responsibility, Resilience, Contribution, Autonomy, Honesty, Care. Red apples = Homeroom System, Student Recognition System, Peer Advisor Program, Round-table Learning. Yellow flowers = Gratitude, Ethics of Living(?), Service etc.
- **Knowledge & Skills**: red apples = Global Citizen Program, Academy, Senior Project, Assembly, Camping. Leaves = ICT, Multiple Intelligences, Metacognition, 4C's (Collaboration/Communication/Creativity/Critical Thinking), plus Problem/Project/Inquiry/Experiential/Lecture methods (small text, partly legible).
- **Practice & Innovation**: red apples = ASB, Club, STEM, Subject Day, Job Shadow, Debate/MUN/HiMCM/ISEF/WSC/CTB/Decathlon-type competitions, Hands-on Ability, Design Thinking, Transdisciplinary Thinking, Global Awareness, Team Spirit, Leadership.
- **Arts & Health** (right canopy): sub-branches **Arts** (Art Festival, Drama Festival, Talent Show, Summer Concert, Lunchtime Music, Fine Art Works Exhibition, Photo Art Exhibition; leaves: Aestheticism, Creation, Identity, Imagination, Musicianship, Craftsmanship, Performance) and **Physical and Mental** (Stallions sports team, Sports Week, First Aid, Fire Drill, Fitness, Rule/Sportsmanship; leaves: Self-concept, Demeanor, Temperament; red apples: Parent School, Parental Workshops, Counseling, Spirit Week).
- Scheduling relevance: LOW (no hours). Confirms venue-locked activity set: Drama Center & Art Gallery, Sports Facilities, labs (see A2).

### A2. PDF p.6 (partial text, 1486 chars) = printed p.4 = `4.webp` — "SHSID Education" mind-map (vision-supplemented)
Center: SHSID Education. Five arms (pypdf garble confirmed/corrected against render):
- **School Mission** (blue): 6 mission bullets (life-long foundations; personal growth; international awareness/multicultural; social skills+methods in Information Age; multilingual skills; math/science/technology emphasis) + 5Cs (Culture Competency, Collaboration, Communication, Creativity, Critical Thinking).
- **Teaching & Learning Strategies** (red): Personalized Course Selection, Hybrid Learning Model, Problem/Project-Based Learning, Roundtable Discussion, Learner Agency.
- **Learning Platforms** (green): Blackboard, Cialfo, SHSID Student Portal, Comprehensive Evaluation System, Personal Growth System.
- **Learning Resources** (teal): Facilities = Innovative Laboratories, Media Center, Libraries, Sports Facilities, Drama Center & Art Gallery; Educational Resources = Textbooks & Teaching Materials, Digital Repertoire, Selected Online Material, Reading List of Different Subjects, Literature Database.
- **Educational Program** (orange): CAS (Creativity, Activity, Service: Ethics of Living, Gratitude, Responsibility, Practice & Service); Personal Growth (Career Planning, Laws & Regulations, Mental Health, Time Management); Outdoor Courses (Survival Training, Team-building Adventure, Embracing Nature, Self-discovery); Well-rounded Development (Performing Arts, Visual Arts, Physical Education, Practical Experiences & Life Skills).
- Scheduling relevance: venue list (labs, Media Center, sports, Drama Center/Art Gallery) + platform constraints (none quantifiable).

### A3. PDF p.7 (350 chars) = printed p.5 = `5.webp` — SHSID High School Curriculum Map + IBD Model
Top figure (person-shaped): head = wheel with CORE COURSES center (Chinese, English, Mathematics, CAS, P.E.) and outer ring Module 1 Lab Sciences / Module 2 Humanities & Social Sciences / Module 3 General Studies / Module 4 Courses of Interest. Body = "Flex" + trapezoid listing Physics, Chemistry, Biology, Chinese, English, Math, History; left arm = Economics, Computer Fundamentals, Human Geography; right arm = Visual Arts, Music Appreciation, Drama; legs = CAS, PE.
Caption: "High School Curriculum Map (Grade 9-12)".
Bottom figure: standard IB Diploma Programme wheel (Studies in Language and Literature, Language Acquisition, Individuals and Societies, Sciences, Mathematics, The Arts; core: TOK/EE/CAS; Approaches to Teaching/Learning; IB Learner Profile; "International-mindedness").
Footnote (exact): "Note: AP and AS/A-Level courses fit into different modules in our high school curriculum map. IBD courses are arranged independently."
Scheduling relevance: **IBD runs on an independent schedule** (reinforced p.6 policy §2.5: IBDP→school/AP transfers "won't be supported because of the schedule confliction").

### A4. PDF p.9 (97 chars, header/footer only) = printed p.7 = `7.webp` — twin-circle curriculum diagram
Top wheel: CORE COURSES center (English, P.E., Mathematics, CAS, Chinese); outer ring Module 1 Lab Sciences / Module 2 Humanities & Social Sciences / Module 3 General Studies / Module 4 Courses of Interest.
Bottom wheel (red/grey): center CORE COURSES + MODULAR COURSES; rings spell out grade placement: Module 1 = G9 Phy.+Chem. / G10 Phy.+Chem./Chem.+Bio./Phy.+Bio.; Module 2 = G9 Bio./Geog./Computer, G10 Econ./Geog./Computer/Music/Arts/Drama; Module 3 = G9 Music/Arts; Module 4 = Grades 9-10 Optionals; outer ring: G9-10 electives incl. Poetry/Prose/Fiction/Plays, Language & Composition, Literary Analysis/Rhetoric, Geometry Function/Trigonometry/Sequences, World History/Chinese History/US History/Western Civilization, Ball games/Water & ice sports/Novel sports/Track & Field/Dancing/Mixed martial arts, Creativity Activity Service, Life Skills/Extended subjects/Languages/Arts/Sports & fitness, Grade 10 PBL/Academy/R-TEW/Study Hall/Beyond.
**Task-label mismatch note:** task called PDF 9 "course selection form continued" — the actual render at printed p.7 is this diagram, no form. (Forms live at printed pp. 8–11 = PDF pp. 10–13, verified below.)

### A5. PDF p.63 (486 chars) = printed p.61 = `61.webp` — sparse Fine-Arts page
Vision confirms page is ~90% blank (watermark + footer only). Sole load-bearing block:
- **Drawing Y2** (ART112E100), Grade 12, Duration: Year, Prereq: Drawing Y1. "Second year of a two-year course… drawing creations… modeling and coloring… personalized education… high level of artworks." Homework: 2 hrs/wk. (Contact periods: not stated.)

