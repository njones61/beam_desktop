# Beam Designer

## Application
Build a Python desktop application with Tkinter. The interface should work
offline and open with an example beam loaded. Keep the interface clean and
professional, with input controls for the beam and its loads, and clear
calculation results and diagrams. Do not depend on a web browser, GitHub Pages,
or external libraries for the desktop interface.

## Purpose
Shear, moment, and deflection diagrams for a beam, with a check of
whether the beam is strong and stiff enough. Educational tool, not for
design of record.

## Design basis
- Allowable stress design (ASD). Bending and shear checks use total
  (dead + live) load.
- Beams are assumed fully laterally braced, and steel sections are assumed
  compact. Buckling is not checked; this is stated on screen.
- US customary units: ft (span, positions), kip and kip/ft (loads),
  in (section properties), ksi (stress).

## Inputs
- Support: simply supported, or cantilever (fixed end at left), and span (ft)
- Point loads: position (ft), magnitude (kip), type (dead or live)
- Uniform loads: start (ft), end (ft), magnitude (kip/ft), type (dead or
  live). Full length is the default; partial spans are allowed.
- Self-weight toggle (default off). When on, it is added as a dead load.
- Section, either:
  - Steel W-shape from a dropdown, with grade selectable:
    A992 (Fy = 50 ksi, default), A36 (Fy = 36 ksi), or a custom Fy
  - Lumber: species/grade and nominal size (see Data)
- Steel sections are drawn to scale under the dropdown (d, bf, tf, tw, x-x
  axis)
- Deflection limit denominator (default 360)

## Calculations
- Reactions, shear, and moment from statics, summing all loads
  (singularity-function superposition, exact for any load mix)
- Deflection by the same method, using E and I of the section
- Bending: fb = M/S, compared to Fb
  - Steel: Fb = 0.66 Fy
  - Lumber: tabulated reference Fb (size factor CF applied; CD = Cr = CL = 1.0)
- Shear: compared to the allowable
  - Steel: fv = V/(d*tw), Fv = 0.4 Fy
  - Lumber: fv = 1.5 V/A, tabulated Fv
- Deflection: live-load-only deflection compared to L/360
  - Cantilever: L is taken as twice the cantilever length
  - Total-load deflection is also shown for information

## Data
- Steel W-shapes: from the AISC Shapes Database, roughly 60-100 common
  shapes (W8-W24): designation, weight (plf), d, bf, tw, tf, A, Ix, Sx, Zx.
  E = 29,000 ksi. Store the data with the Python application; note the source
  file and version in 01_data/.
- Lumber: dimension lumber only (2x4-2x12 and 4x4-4x12), actual sizes
  (e.g. 2x10 = 1.5 x 9.25 in), reference values from the NDS Supplement
  Table 4A. Starting species/grades, all No. 2:
  - Douglas Fir-Larch
  - Southern Pine (Fb varies with member width in the table)
  - Hem-Fir
  - Spruce-Pine-Fir
  Per species: Fb, Fv, E, CF by size, and density for self-weight.
  Values are checked against the published tables before use.
- Sections shown with their properties (A, I, S) so results can be traced.

## Outputs
- The beam with its loads, and the three diagrams on a shared x-axis, with
  a hover readout of V, M, and deflection at any point
- Reactions; max V, max M, and max deflection with their locations
- Pass or fail for bending, shear, and deflection, each with its ratio
  (fb/Fb, fv/Fv, deflection/limit)
- Sign convention and assumptions shown on screen

## Save and open
- A File menu provides Save and Open for beam designs stored locally. Save and
  restore the support, span, section and grade, custom Fy, deflection limit,
  self-weight setting, and point and uniform loads with their types.

## Look and feel
Clean and professional Tkinter desktop interface, with an example beam loaded
when it opens. Draw the beam and diagrams within the desktop application.
Keep the application usable offline.

## Validation
All cases have hand calculations in 02_validation/.
- 20 ft simply supported W12x26, 1 kip/ft live, self-weight off:
  M = 50.0 kip-ft, deflection 0.609 in (Ix = 204 in4), fb = 50*12/33.4 =
  17.96 ksi. Deflection limit 240/360 = 0.667 in, so ratio about 0.91 (pass).
- Midspan point load, simply supported: M = PL/4, deflection = PL^3/48EI
- Off-center point load: reactions by moments
- Cantilever tip load: M = PL, deflection = PL^3/3EI
- Cantilever with uniform load: M = wL^2/2, deflection = wL^4/8EI
- Mixed point plus partial uniform load: checks superposition
- A lumber beam: checks actual-size properties and CF
- Dead/live split: deflection uses live load only, stresses use both

## Out of scope
Continuous beams, indeterminate cases (fixed-fixed, propped cantilever),
overhangs, applied moments, load combinations, lateral-torsional and local
buckling, bearing and web crippling, torsion, creep, connections, 6x and
larger timbers, glulam and engineered lumber.
