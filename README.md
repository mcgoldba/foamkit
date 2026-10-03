FoamKit
-------

Pythonic modification of OpenFOAM dictionaries and case files.

Features
--------

* Load OpenFOAM cases as Python objects
* Read and edit OpenFOAM dictionary entries
* Manipulated OpenFOAM cases from command line using the integrated iPython console
* Manipulate OpenFOAM cases from a Python script file.
* Support for most OpenFOAM naitive types including:
    * dictonary entries, lists, scalars, vectors, tensors, dimensioned types, tables, coded objects, and more
* Run OpenFOAM case Allrun scripts
* Easily setup and execute parametric OpenFOAM studies with many simulations     

Installation
------------

```bash
#terminal
python -m pip install foamkit
```

Basic Usage
-----------

Copy a template case and load as a python object
```bash
#terminal
cp $FOAM_TUTORIALS/incompressible/simpleFoam/pitzDaily .
cd pitzDaily
pf init
```

View case variables
```bash
#terminal
pf edit
```

```python
#Python console
>>> case.constant.turbulenceProperties.RAS.RASModel
kEpsilon
```
Change case dictionary entries

```python
#Python console
>>> case.constant.case.constant.turbulenceProperties.RAS.RASModel = kOmega
```

Write the updated case to file

```python
#Python console
>>> case.write()
```

Run the Allrun script
```python
#Python console
>>> case.run()
```

Scripting
---------

FoamKit can also be imported into a python script to allow for manipultion of OpenFOAM cases.  This is useful, for example, when performing parameteric studies to run multiple simulations with varibale parameters (e.g. different turbulence models):

```bash
#terminal
#- Setup the OpenFOAM study directory
cd ~
mkdir ofStudy
cd ofStudy
cp $FOAM_TEMPLATES/incompressible/simpleFoam/pitzDaily of.template
touch runStudy.py
```

runStudy.py
```python
import foamkit.functions as pf
import foamkit.types as pt
import pamdas as pd

turbulenceModels = [kEpsilon, realizableKE, kOmega, kOmegaSST]
parameterNames = ['Turbulence Model']

samples = pd.DataFrame(
    [[model] for model in turbulenceModels],
    columns = parameterNames
)

def updateCase(case, values):
    """
    This function is called from the ofStudy.

    Parameters
    ----------
    case [foamkit.ofCase]:
        The OpenFOAM case which is to be updated.
    values [list]:
        Sample point as a list of dictionary values to be updated for the current simulation

    Return
    ------
    case [foamkit.ofCase]:
        The updated OpenFOAM case.
        
    """
    turbModel = values[0]

    case.constant.case.constant.turbulenceProperties.RAS.RASModel = turbModel

    return case

#- Create the OpenFOAM study
study = pt.ofStudy('of.template', parameterNames, sample, updateCase)

#- Run all 4 simulations
study.run()
 
```

```bash
#terminal
# Run the study
python runStudy.py
```

Releasing
---------

Releases are published automatically when a tag is pushed to GitHub.

```bash
# Set next version number
export RELEASE=x.x.x

# Create tags
git commit --allow-empty -m "Release $RELEASE"
git tag -a $RELEASE -m "Version $RELEASE"

# Push
git push upstream --tags
```
