# IMPORTS 
import os
import re
import numpy as np
import slicer
import qt
import ctk

# numpy
try:
    import numpy as np
except:
    slicer.util.pip_install('nibabel')
    import numpy as np

# nibabel
try:
    import nibabel as nib
except:
    slicer.util.pip_install('nibabel')
    import nibabel as nib

# matplotlib
try:
    import matplotlib.pyplot as plt
except:
    slicer.util.pip_install('matplotlib')
    import matplotlib.pyplot as plt

# SimpleITK 
try:
    import SimpleITK as sitk
except:
    slicer.util.pip_install('SimpleITK')
    import SimpleITK as sitk
    
# wtk
try:
    import vtk
except:
    slicer.util.pip_install('vtk')
    import vtk
    
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleWidget,
    ScriptedLoadableModuleLogic,
)


class waxholm(ScriptedLoadableModule):
    """
    description
    """
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent.title = "Waxholm Atlas Auto Segmenter"
        self.parent.categories = ["Segmentation"]
        self.parent.contributors = ["Generated from notebook workflow"]


class waxholmWidget(ScriptedLoadableModuleWidget):

    def setup(self):
        super().setup()

        self.logic = waxholmLogic()

        form = qt.QFormLayout()

        self.subjectSelector = slicer.qMRMLNodeComboBox()
        self.subjectSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
        self.subjectSelector.setMRMLScene(slicer.mrmlScene)
        form.addRow("Subject MRI", self.subjectSelector)

        self.atlasSelector = slicer.qMRMLNodeComboBox()
        self.atlasSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
        self.atlasSelector.setMRMLScene(slicer.mrmlScene)
        form.addRow("Atlas MRI", self.atlasSelector)

        self.labelSelector = slicer.qMRMLNodeComboBox()
        self.labelSelector.nodeTypes = ["vtkMRMLLabelMapVolumeNode",
                                        "vtkMRMLScalarVolumeNode"]
        self.labelSelector.setMRMLScene(slicer.mrmlScene)
        form.addRow("Atlas Label Volume", self.labelSelector)

        self.labelFilePicker = ctk.ctkPathLineEdit()
        form.addRow("Waxholm .label file", self.labelFilePicker)

        self.loadStructuresButton = qt.QPushButton("Load Structures")
        form.addRow(self.loadStructuresButton)

        self.regionCombo = qt.QComboBox()
        form.addRow("Region", self.regionCombo)

        self.exportQC = qt.QCheckBox("Export JPEG QC Images")
        form.addRow(self.exportQC)
        
        self.affine = qt.QCheckBox("Use Affine Registration")
        form.addRow(self.affine)

        self.generateButton = qt.QPushButton("Generate Segmentation")
        form.addRow(self.generateButton)

        self.layout.addLayout(form)
        self.layout.addStretch(1)

        self.loadStructuresButton.connect(
            "clicked()",
            self.onLoadStructures
        )

        self.generateButton.connect(
            "clicked()",
            self.onGenerate
        )

    def onLoadStructures(self):

        self.regionCombo.clear()

        path = self.labelFilePicker.currentPath
        structures = self.logic.parseLabelFile(path)

        for labelId, name in structures:
            self.regionCombo.addItem(
                f"{name} ({labelId})",
                labelId
            )

    def onGenerate(self):

        subject = self.subjectSelector.currentNode()
        atlas = self.atlasSelector.currentNode()
        labels = self.labelSelector.currentNode()

        labelId = self.regionCombo.currentData
        
        # FIX: retrieve as string (matches how it was stored), then convert
        labelId = self.regionCombo.currentData
        if labelId is None:
            slicer.util.errorDisplay("No region selected.")
            return

        labelId = int(labelId)

        print(f"Running segmentation for label ID: {labelId}")

        self.logic.generateSegmentation(
            subject,
            atlas,
            labels,
            labelId,
            exportQC = self.exportQC.checked,
            do_affine = self.affine.checked
        )


class waxholmLogic(ScriptedLoadableModuleLogic):
    """
    meow
    """
    
    def parseLabelFile(self, filename):

        structures = []

        if not os.path.exists(filename):
            return structures

        with open(filename, "r", errors="ignore") as f:

            for line in f:

                nums = re.findall(r"\d+", line)

                if len(nums) < 1:
                    continue

                try:
                    labelId = int(nums[0])
                except:
                    continue

                text = line.strip()

                structures.append((labelId, text))

        return structures
    
    """
    meow
    """
    def registration(
        self,
        subjectVolumeNode,
        atlasVolumeNode,
        atlasLabelNode,
        labelId,
    ):
        pass
        
        
    """
    meow
    """ 
    def generateSegmentation(
        self,
        subjectVolumeNode,
        atlasVolumeNode,
        atlasLabelNode,
        labelId,
        exportQC = False,
        do_affine = False
    ):

        subjectArray = slicer.util.arrayFromVolume(
            subjectVolumeNode
        )

        atlasArray = slicer.util.arrayFromVolume(
            atlasVolumeNode
        )

        labelArray = slicer.util.arrayFromVolume(
            atlasLabelNode
        )

        # Creating mask for the specified label ID
        mask = (labelArray == int(labelId)).astype(np.uint8)
        
        mask_sitk = sitk.GetImageFromArray(mask.astype(np.uint8))

        mask_sitk.SetSpacing(atlasLabelNode.GetSpacing())
        mask_sitk.SetOrigin(atlasLabelNode.GetOrigin())
        mask_sitk.SetDirection(
            getDirectionFromVolumeNode(atlasLabelNode)
        )

        # Read with SimpleITK
        atlas_t2_sitk = sitk.GetImageFromArray(atlasArray)
        mri_sitk = sitk.GetImageFromArray(subjectArray)
        
        atlas_t2_sitk = sitk.Cast(atlas_t2_sitk, sitk.sitkFloat32) # debugging CenteredTransformInitializer
        mri_sitk = sitk.Cast(mri_sitk, sitk.sitkFloat32)
        
        atlas_t2_sitk.SetSpacing(atlasVolumeNode.GetSpacing())
        atlas_t2_sitk.SetOrigin(atlasVolumeNode.GetOrigin())

        mri_sitk.SetSpacing(subjectVolumeNode.GetSpacing())
        mri_sitk.SetOrigin(subjectVolumeNode.GetOrigin())
        
        atlas_t2_sitk.SetDirection(
            getDirectionFromVolumeNode(atlasVolumeNode)
        )

        mri_sitk.SetDirection(
            getDirectionFromVolumeNode(subjectVolumeNode)
        )
        
        """ # debug
        print("================================")
        print("Subject array shape:", subjectArray.shape)
        print("Atlas array shape:", atlasArray.shape)
        print("Label array shape:", labelArray.shape)

        print("Subject dtype:", subjectArray.dtype)
        print("Atlas dtype:", atlasArray.dtype)

        print("Subject SITK dimension:", mri_sitk.GetDimension())
        print("Atlas SITK dimension:", atlas_t2_sitk.GetDimension())

        print("Subject SITK size:", mri_sitk.GetSize())
        print("Atlas SITK size:", atlas_t2_sitk.GetSize())

        print("Subject node class:", subjectVolumeNode.GetClassName())
        print("Atlas node class:", atlasVolumeNode.GetClassName())
        print("================================")
        
        print("Subject PixelID:", mri_sitk.GetPixelIDTypeAsString())
        print("Atlas PixelID:", atlas_t2_sitk.GetPixelIDTypeAsString())
        
        print("Subject spacing:", mri_sitk.GetSpacing())
        print("Atlas spacing:", atlas_t2_sitk.GetSpacing())
        
        print("Subject dimension:", mri_sitk.GetDimension())
        print("Atlas dimension:", atlas_t2_sitk.GetDimension())

        print("Subject components:", mri_sitk.GetNumberOfComponentsPerPixel())
        print("Atlas components:", atlas_t2_sitk.GetNumberOfComponentsPerPixel())

        print("MRI type:", mri_sitk)
        print("Atlas type:", atlas_t2_sitk)
        """

        # Initial alignment (centered)
        initial_tx = sitk.CenteredTransformInitializer(
            mri_sitk,
            atlas_t2_sitk,
            sitk.Euler3DTransform(),
            sitk.CenteredTransformInitializerFilter.GEOMETRY
        )

        # Set up registration (Mattes MI + gradient descent)
        reg = sitk.ImageRegistrationMethod()
        reg.SetMetricAsMattesMutualInformation(50)
        reg.SetMetricSamplingStrategy(reg.RANDOM)
        reg.SetMetricSamplingPercentage(0.2)
        reg.SetInterpolator(sitk.sitkLinear)
        reg.SetOptimizerAsRegularStepGradientDescent(learningRate=2.0,
                                                     minStep=1e-4,
                                                     numberOfIterations=200,
                                                     relaxationFactor=0.5)
        reg.SetOptimizerScalesFromPhysicalShift()
        reg.SetInitialTransform(initial_tx, inPlace=False)

        final_rigid = reg.Execute(mri_sitk, atlas_t2_sitk)
        print("Rigid registration done. Metric:", reg.GetMetricValue())

        # (Optional) Affine refinement
        if do_affine:
            affine = sitk.AffineTransform(final_rigid)
            reg2 = sitk.ImageRegistrationMethod()
            reg2.SetMetricAsMattesMutualInformation(50)
            reg2.SetMetricSamplingStrategy(reg2.RANDOM)
            reg2.SetMetricSamplingPercentage(0.2)
            reg2.SetInterpolator(sitk.sitkLinear)
            reg2.SetOptimizerAsRegularStepGradientDescent(1.0, 1e-4, 200, 0.5)
            reg2.SetInitialTransform(affine, inPlace=False)
            final_tx = reg2.Execute(mri_sitk, atlas_t2_sitk)
            print("Affine refinement done. Metric: ", reg2.GetMetricValue())
        else:
            final_tx = final_rigid

        # Resample to MRI space using nearest-neighbor (preserve labels)
        resampledMask = sitk.Resample(
            mask_sitk,
            mri_sitk,
            final_tx,
            sitk.sitkNearestNeighbor,
            0,
            sitk.sitkUInt8
        )

        # who knows what's happening after here
        maskMRI = sitk.GetArrayFromImage(resampledMask).astype(np.uint8)

        labelmapNode = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLLabelMapVolumeNode",
            "WaxholmMask"
        )

        slicer.util.updateVolumeFromArray(
            labelmapNode,
            maskMRI
        )

        labelmapNode.CopyOrientation(subjectVolumeNode)

        segNode = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLSegmentationNode",
            f"Label_{labelId}"
        )

        segNode.SetReferenceImageGeometryParameterFromVolumeNode(
            subjectVolumeNode
        )

        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(
            labelmapNode,
            segNode
        )

        segNode.CreateClosedSurfaceRepresentation()

        slicer.mrmlScene.RemoveNode(labelmapNode)

        return segNode

def getDirectionFromVolumeNode(volumeNode):
    """
    helper function
    """
    
    m = vtk.vtkMatrix4x4()
    volumeNode.GetIJKToRASDirectionMatrix(m)

    return (
        m.GetElement(0,0), m.GetElement(0,1), m.GetElement(0,2),
        m.GetElement(1,0), m.GetElement(1,1), m.GetElement(1,2),
        m.GetElement(2,0), m.GetElement(2,1), m.GetElement(2,2),
    )