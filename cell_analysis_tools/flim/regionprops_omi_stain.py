#%%
from pprint import pprint

import matplotlib as mpl
import matplotlib.pylab as plt
import numpy as np
import numpy.ma as ma
import tifffile
from skimage.measure import regionprops
from skimage.morphology import label

from cell_analysis_tools.image_processing import normalize
from cell_analysis_tools.io import read_asc

mpl.rcParams["figure.dpi"] = 300
import math


#%%
def regionprops_omi_run(
    Intensity_weighted_means: bool,
    Stain_intensity: bool,
    Stain_lifetime: bool,
    FAD: bool,
    image_id: str,  # base_name of image
    label_image: np.ndarray,
    im_nadh_intensity: np.ndarray = None,
    im_nadh_a1: np.ndarray = None,
    im_nadh_a2: np.ndarray = None,
    im_nadh_t1: np.ndarray = None,
    im_nadh_t2: np.ndarray = None,
    im_fad_intensity: np.ndarray = None,
    im_fad_a1: np.ndarray = None,
    im_fad_a2: np.ndarray = None,
    im_fad_t1: np.ndarray = None,
    im_fad_t2: np.ndarray = None,
    im_nadh_chi: np.ndarray = None,
    im_fad_chi: np.ndarray = None,
    im_stain_intensity: np.ndarray = None,
    im_stain_a1 : np.ndarray = None,
    im_stain_a2 : np.ndarray = None,
    im_stain_t1 : np.ndarray = None,
    im_stain_t2 : np.ndarray = None,
    other_props: list = None,
) -> dict:
    #%%
    """
    Takes in labels image as well as nadh and fad images from SPCImage to return
    mean and stdev of each parameter per roi. 

    Parameters
    ----------
        label_image : ndarray
            labeled mask image.
        im_nadh_intensity : ndarray
            nadh intensity image.
        im_nadh_a1 : ndarray
            nadh alpha1 image.
        im_nadh_a2 : ndarray
            nadh alpha2 image .
        im_nadh_t1 : ndarray
            nadh tau 1 lifetime, short .
        im_nadh_t2 : ndarray
            nadh tau 2 lifetime, long.
        im_fad_intensity : ndarray
            nadh intensity image. 
        im_fad_a1 : ndarray
            fad alpha 1 image. 
        im_fad_a2 : ndarray
            fad alpha 2 image. 
        im_fad_t1 : ndarray
            fad tau 1 lifetime, long. 
        im_fad_t2 : ndarray
            fad tau 2 lifetime, short.
        other_props : list
            string list of additional parameters to compute on the binary mask
            see skimage regionprops for list of attributes 
    
    .. note::
        See `https://scikit-image.org/docs/dev/api/skimage.measure.html#skimage.measure.regionprops <https://scikit-image.org/docs/dev/api/skimage.measure.html#skimage.measure.regionprops>`_
        for a list of additiona properties you can compute
        
        
    Returns
    -------
    dict
        dictionary of mean and standard deviations of 
        omi parameters for each region.

    """
    # 1. nadh_intensity
    # 2. nadh_a1
    # 3. nadh_a2
    # 4. nadh_t1
    # 5. nadh_t2
    # 6. nadh_tau_mean
    # 7. fad_intensity
    # 8. fad_a1
    # 9. fad_a2
    # 10. fad_t1
    # 11. fad_t2
    # 12. fad_tau_mean
    # 13. redox_ratio

    ##%%
    # compute composite images not generated by SPCImage, also convert a1/a2 to percent
    if (
        im_nadh_a1 is not None
        and im_nadh_a2 is not None
        and im_nadh_t1 is not None
        and im_nadh_t2 is not None
    ):
        im_nadh_tau_mean = (im_nadh_a1 / 100 * im_nadh_t1) + (
            im_nadh_a2 / 100 * im_nadh_t2
        )
    else:
        im_nadh_tau_mean = None
    if FAD==True:
        if (
            im_fad_a1 is not None
            and im_fad_a2 is not None
            and im_fad_t1 is not None
            and im_fad_t2 is not None
        ):
            im_fad_tau_mean = (im_fad_a1 / 100 * im_fad_t1) + (im_fad_a2 / 100 * im_fad_t2)
        else:
            im_fad_tau_mean = None

    # COMPUTE REDOX RATIO
    # create masked arrays so it doesn't affect averaging
        if im_fad_intensity is not None and im_nadh_intensity is not None:
            labels_inverted = np.invert(label_image.astype(bool))
            masked_im_fad_intensity = ma.masked_array(
                im_fad_intensity, mask=labels_inverted)
            masked_im_nadh_intensity = ma.masked_array(
                im_nadh_intensity, mask=labels_inverted)
    
            # compute both types of redox ratios
            im_redox_ratio = masked_im_nadh_intensity / masked_im_fad_intensity
            im_redox_ratio_norm = masked_im_nadh_intensity / (
                masked_im_fad_intensity + masked_im_nadh_intensity)
        else:
            im_redox_ratio = None
            im_redox_ratio_norm = None

    # COMPUTE FLIRR
    # fluorescence lifetime imaging redox ratio aka FLIRR
    # labels mask image should not include any im_fad_a1 zeros
    # apply mask then compute to avoid Infinite values

        if im_fad_a1 is not None and im_nadh_a2 is not None:
            masked_im_fad_a1 = ma.masked_array(im_fad_a1, mask=labels_inverted)
            masked_im_nadh_a2 = ma.masked_array(im_nadh_a2, mask=labels_inverted)
            im_flirr = (masked_im_nadh_a2 / 100) / (
                masked_im_fad_a1 / 100
            )  # bound portions of NADH/FAD
    
            if im_flirr.any() == np.inf:
                print(
                    "regionprops_omi: INF values found in FLIRR image, they will be set to zero"
                )
                im_flirr[im_flirr == np.inf] = 0
        else:
            im_flirr = None

    # define extra functions for properties
    def stdev(roi, intensity):
        inverted_roi = np.invert(roi.astype(bool))
        masked_image = ma.masked_array(intensity, mask=inverted_roi)
        return np.std(masked_image)

    def chi_median(roi, intensity):
        inverted_roi = np.invert(roi.astype(bool))
        masked_image = ma.masked_array(intensity, mask=inverted_roi)
        # plt.imshow(masked_image, vmax=1.5)
        return ma.median(masked_image)  # np.median looks at masked values

    extra_properties = [stdev, chi_median]

    # COMPUTE REGIONPROPS JUST ON BINARY IMAGE
    mask_props = regionprops(label_image)

    dict_regionprops = {}

    # COMPUTE EQUALLY WEIGHTED PARAMETERS AND ASSEMBLE DICT OF REGIONPROPS
    if im_nadh_intensity is not None:
        nadh_intensity = regionprops(
            label_image, im_nadh_intensity, extra_properties=extra_properties)
        dict_regionprops["nadh_intensity"] = nadh_intensity
    if im_nadh_a1 is not None:
        nadh_a1 = regionprops(
            label_image, im_nadh_a1, extra_properties=extra_properties)
        dict_regionprops["nadh_a1"] = nadh_a1
    if im_nadh_a2 is not None:
        nadh_a2 = regionprops(label_image, im_nadh_a2, extra_properties=extra_properties)
        dict_regionprops["nadh_a2"] = nadh_a2
    if im_nadh_t1 is not None:
        nadh_t1 = regionprops(
            label_image, im_nadh_t1, extra_properties=extra_properties)
        dict_regionprops["nadh_t1"] = nadh_t1
    if im_nadh_t2 is not None:
        nadh_t2 = regionprops(
            label_image, im_nadh_t2, extra_properties=extra_properties)
        dict_regionprops["nadh_t2"] = nadh_t2
    if im_nadh_tau_mean is not None:
        nadh_tau_mean = regionprops(
            label_image, im_nadh_tau_mean, extra_properties=extra_properties)
        dict_regionprops["nadh_tau_mean"] = nadh_tau_mean
        
    if FAD == True:

        if im_fad_intensity is not None:
            fad_intensity = regionprops(label_image, im_fad_intensity, extra_properties=extra_properties)
            dict_regionprops["fad_intensity"] = fad_intensity
        if im_fad_a1 is not None:
            fad_a1 = regionprops(label_image, im_fad_a1, extra_properties=extra_properties)
            dict_regionprops["fad_a1"] = fad_a1
        if im_fad_a2 is not None:
            fad_a2 = regionprops(label_image, im_fad_a2, extra_properties=extra_properties)
            dict_regionprops["fad_a2"] = fad_a2
        if im_fad_t1 is not None:
            fad_t1 = regionprops(label_image, im_fad_t1, extra_properties=extra_properties)
            dict_regionprops["fad_t1"] = fad_t1
        if im_fad_t2 is not None:
            fad_t2 = regionprops(label_image, im_fad_t2, extra_properties=extra_properties)
            dict_regionprops["fad_t2"] = fad_t2
        if im_fad_tau_mean is not None:
            fad_tau_mean = regionprops(
                label_image, im_fad_tau_mean, extra_properties=extra_properties)
            dict_regionprops["fad_tau_mean"] = fad_tau_mean
    
        if im_redox_ratio is not None:
            redox_ratio = regionprops(
                label_image, im_redox_ratio, extra_properties=extra_properties)
            dict_regionprops["redox_ratio"] = redox_ratio
        if im_redox_ratio_norm is not None:
            redox_ratio_norm = regionprops(
                label_image, im_redox_ratio_norm, extra_properties=extra_properties)
            dict_regionprops["redox_ratio_norm"] = redox_ratio_norm
        if im_flirr is not None:
            flirr = regionprops(
                label_image, im_flirr, extra_properties=extra_properties)
            dict_regionprops["flirr"] = flirr
            
    if Stain_intensity == True:
        if im_stain_intensity is not None:
            stain_intensity = regionprops(
                label_image, im_stain_intensity, extra_properties=extra_properties)
            dict_regionprops["stain_intensity"] = stain_intensity
        
    if Stain_lifetime == True: 
        if im_stain_a1 is not None:
            stain_a1 = regionprops(label_image, im_stain_a1, extra_properties=extra_properties)
            dict_regionprops["stain_a1"] = stain_a1
        if im_stain_a2 is not None:
            stain_a2 = regionprops(label_image, im_stain_a2, extra_properties=extra_properties)
            dict_regionprops["stain_a2"] = stain_a2
        if im_stain_t1 is not None:
            stain_t1 = regionprops(label_image, im_stain_t1, extra_properties=extra_properties)
            dict_regionprops["stain_t1"] = stain_t1
        if im_stain_t2 is not None:
            stain_t2 = regionprops(label_image, im_stain_t2, extra_properties=extra_properties)
            dict_regionprops["stain_t2"] = stain_t2

    # add chi squared values if passed in
    bool_has_chi_images = False
    if im_nadh_chi is not None and im_fad_chi is not None:
        bool_has_chi_images = True
        nadh_chi = regionprops(
            label_image, im_nadh_chi, extra_properties=extra_properties
        )
        fad_chi = regionprops(
            label_image, im_fad_chi, extra_properties=extra_properties
        )
        dict_regionprops["nadh_chi"] = nadh_chi  # add regionprops
        dict_regionprops["fad_chi"] = fad_chi  # add regionprops

    # assemble dictionary of omi parameters
    dict_omi = {}
    for rp_key in dict_regionprops.keys():  # iterate through each images regionprops
        pass
        for region in dict_regionprops[rp_key]:  # iterate through region in regionprops
            pass
            # print(region)
            dict_key_name = f"{image_id}_{region.label}"  # generate unique key for region in this image
            if not dict_key_name in dict_omi.keys():  # add region dict if needed
                pass
                dict_omi[dict_key_name] = {}  # add new dict for this label
                dict_omi[dict_key_name]["mask_label"] = int(
                    region.label
                )  # save label value

            # save equally weighted parameters
            dict_omi[dict_key_name][f"{rp_key}_mean"] = region.mean_intensity
            dict_omi[dict_key_name][f"{rp_key}_stdev"] = region.stdev

            # save chi squared median value
            if bool_has_chi_images and rp_key == "nadh_chi" or rp_key == "fad_chi":
                dict_omi[dict_key_name][f"{rp_key}_median"] = region.chi_median

            ### COMPUTE INTENSITY WEIGHTED VALUES
            if Intensity_weighted_means==True:
                # make a list of files it makes sense to compute weighted values for
                list_valid_intensity_weights = [
                    "nadh_a1",
                    "nadh_a2",
                    "nadh_t1",
                    "nadh_t2",
                    "nadh_tau_mean",
                    "fad_a1",
                    "fad_a2",
                    "fad_t1",
                    "fad_t2",
                    "fad_tau_mean",
                ]
    
                if (
                    rp_key in list_valid_intensity_weights
                ):  # iterate through valid lifetime images
                    pass
                    # select proper intensity image to weigh by, find roi by region.label
                    if "fad" in rp_key and im_fad_intensity is not None:
                        im_intensity_region = [
                            r for r in fad_intensity if r.label == region.label
                        ][
                            0
                        ]  # should be one region
    
                    elif "nadh" in rp_key and im_nadh_intensity is not None:
                        im_intensity_region = [
                            r for r in nadh_intensity if r.label == region.label
                        ][
                            0
                        ]  # should be one region
    
                    else:
                        continue  # skip this set
                    # gather other things needed for intensity weighted
                    binary = region.image
                    inverted_binary = np.invert(binary)
    
                    im_lifetime_masked = ma.masked_array(
                        region.intensity_image, mask=inverted_binary
                    )
                    im_intensity_masked = ma.masked_array(
                        im_intensity_region.intensity_image, mask=inverted_binary
                    )
    
                    # Kayvans way of avg weighing image
                    intensity_weighted_mean = np.sum(
                        im_lifetime_masked * im_intensity_masked
                    ) / np.sum(im_intensity_masked)
    
                    # https://stackoverflow.com/questions/2413522/weighted-standard-deviation-in-numpy
                    def weighted_avg_and_std(values, weights):
                        """
                        Return the weighted average and standard deviation.
                        values, weights -- Numpy ndarrays with the same shape.
                        """
                        average = np.average(values, weights=weights)
    
                        # Fast and numerically precise:
                        variance = np.average((values - average) ** 2, weights=weights)
                        return (average, math.sqrt(variance))
    
                    try:
                        weighted_mean, weighted_stdev = weighted_avg_and_std(
                            im_lifetime_masked, im_intensity_masked
                            )
                    except ZeroDivisionError as err:
                        weighted_mean = 0
                        weighted_stdev = 0
    
                    # assert weighted_mean == intensity_weighted_mean
    
                    # save values
                    dict_omi[dict_key_name][
                        f"{rp_key}_intensity_weighted_mean"
                    ] = intensity_weighted_mean
                    dict_omi[dict_key_name][
                        f"{rp_key}_intensity_weighted_stdev"
                    ] = weighted_stdev
               

            ### Done adding intensity weighted params

    # ADD OTHER PARAMETERS (area, eccentricity, etc...)
    if other_props is not None and len(other_props) != 0:
        for region in mask_props:  # iterate through region in regionprops
            pass
            dict_key_name = f"{image_id}_{region.label}"  # generate unique key for region in this image
            # mask_region = [r for r in mask_props if r.label == region.label][0]
            for prop in other_props:
                dict_omi[dict_key_name][prop] = region[prop]


    #%%
    # dictionary of omi features
    return dict_omi
