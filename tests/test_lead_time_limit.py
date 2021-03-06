import matplotlib
matplotlib.use("Agg")

import os
from dnaweaver import (PcrOutStation,
                       CommercialDnaOffer,
                       DnaAssemblyStation,
                       GibsonAssemblyMethod,
                       GoldenGateAssemblyMethod,
                       BuildAGenomeAssemblyMethod,
                       DnaSourcesComparator,
                       TmOverhangSelector,
                       FixedSizeOverhangSelector,
                       PerBasepairPricing,
                       NoPatternConstraint,
                       SequenceLengthConstraint)
from dnaweaver.biotools import gc_content
from dnaweaver.reports import (JsonQuote, make_folder_report,
                               autocolor_quote_sources)

SEQUENCE_PATH = os.path.join('tests', 'data', 'full_example_50kb_sequence.txt')
ECOLI_DB_PATH = os.path.join('tests', 'data', 'ecoli_blast_db', 'ecoli')

def test_full_report():

    # OLIGO COMPANIES

    a_star_factor = 'auto'
    memoize = True

    oligo_com = CommercialDnaOffer(
        name="Oligo.com",
        sequence_constraints=[SequenceLengthConstraint(max_length=200)],
        pricing=PerBasepairPricing(0.10),
        lead_time=7
    )

    deluxe_dna_com = CommercialDnaOffer(
        name="DeluxeDNA.com",
        sequence_constraints=[SequenceLengthConstraint(max_length=4000)],
        pricing=PerBasepairPricing(0.20),
        lead_time=10
    )

    cheap_dna_com = CommercialDnaOffer(
        name="CheapDNA.com",
        sequence_constraints=[SequenceLengthConstraint(max_length=4000),
                              NoPatternConstraint(enzyme='AarI'),
                              NoPatternConstraint(enzyme='BsaI'),
                              lambda seq: (0.4 < gc_content(seq) < 0.6)
                              ],
        pricing=PerBasepairPricing(0.10),
        lead_time=15
    )

    # OLIGOS TO BLOCKS ASSEMBLY

    oligo_assembly_station = DnaAssemblyStation(
        name="Oligo Assembly Station",
        assembly_method=BuildAGenomeAssemblyMethod(
            overhang_selector=TmOverhangSelector(
                min_size=15, max_size=25, min_tm=50, max_tm=70),
            min_segment_length=40,
            max_segment_length=200,
            sequence_constraints=[SequenceLengthConstraint(max_length=1500)],
            duration=8,
            cost=2
        ),
        dna_source=oligo_com,
        coarse_grain=20,
        fine_grain=False,
        a_star_factor=a_star_factor
    )

    # BLOCKS TO CHUNKS ASSEMBLY

    blocks_sources_comparator = DnaSourcesComparator(
        name='bs_comparator',
        suppliers=[
            oligo_assembly_station,
            cheap_dna_com,
            deluxe_dna_com
        ],
        memoize=memoize
    )

    gibson_blocks_assembly_station = DnaAssemblyStation(
        name="Gibson Blocks Assembly",
        assembly_method=GibsonAssemblyMethod(
            overhang_selector=FixedSizeOverhangSelector(80),
            min_segment_length=1000,
            max_segment_length=4000,
            duration=8,
            cost=16
        ),
        dna_source=blocks_sources_comparator,
        coarse_grain=300,
        fine_grain=False,
        memoize=memoize,
        a_star_factor=a_star_factor
    )

    goldengate_blocks_assembly_station = DnaAssemblyStation(
        name="Golden Gate Blocks Assembly",
        assembly_method=GoldenGateAssemblyMethod(
            enzyme='BsmBI',
            wildcard_basepair="A",
            min_segment_length=1000,
            max_segment_length=4000,
            duration=5,
            cost=6
        ),
        dna_source=blocks_sources_comparator,
        coarse_grain=400,
        fine_grain=False,
        memoize=memoize,
        a_star_factor=a_star_factor
    )

    ecoli_genome = PcrOutStation(
        "E. coli Genome (PCR)",
        primers_dna_source=oligo_com,
        blast_database=ECOLI_DB_PATH,
        max_amplicon_length=10000,
        extra_time=3,
        extra_cost=1
    )

    # CHUNKS TO MEGACHUNKS ASSEMBLY

    chunks_assembly_station = DnaAssemblyStation(
        name="Chunks assembly (Gibson)",
        assembly_method=GibsonAssemblyMethod(
            overhang_selector=FixedSizeOverhangSelector(300),
            min_segment_length=7000,
            max_segment_length=25000,
            duration=8
        ),
        dna_source=DnaSourcesComparator([
            ecoli_genome,
            goldengate_blocks_assembly_station,
            gibson_blocks_assembly_station,

        ]),
        coarse_grain=1000,
        fine_grain=None,
        logger='bars',
        a_star_factor=a_star_factor,
        memoize=memoize
    )

    with open(SEQUENCE_PATH, "r") as f:
        sequence = f.read()

    import time
    t0 = time.time()

    ecoli_genome.pre_blast(sequence)
    quote = chunks_assembly_station.get_quote(
        sequence, max_lead_time=28, with_assembly_plan=True)

    t1 = time.time()
    print("ELAPSED:", "%.02f" % (t1 - t0))
    print(quote)

    if quote.accepted:
        print(quote.assembly_step_summary())
    assert (4400 < quote.price < 4600)
